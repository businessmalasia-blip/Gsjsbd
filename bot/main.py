import asyncio
import logging

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.handlers import start, tickets, lists, reports, logs, admin
from bot.handlers.export import run_daily_export
from bot.middlewares.auth import AuthMiddleware
from config import settings
from database.connection import create_tables, async_session_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SessionMiddleware:
    async def __call__(self, handler, event, data):
        async with async_session_factory() as session:
            data["session"] = session
            return await handler(event, data)


async def main():
    await create_tables()
    logger.info("Database tables created/verified.")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares (order matters)
    dp.message.middleware(SessionMiddleware())
    dp.callback_query.middleware(SessionMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routers
    dp.include_router(start.router)
    dp.include_router(tickets.router)
    dp.include_router(lists.router)
    dp.include_router(reports.router)
    dp.include_router(logs.router)
    dp.include_router(admin.router)

    # Daily export scheduler — fires at 10:00 Moscow time every day
    tz = pytz.timezone(settings.TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        run_daily_export,
        CronTrigger(hour=11, minute=37, timezone=tz),
        args=[bot],
        id="daily_export",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Daily export at 10:00 %s", settings.TIMEZONE)

    logger.info("Starting CRM bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
