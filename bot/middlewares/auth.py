from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import get_operator_by_telegram_id
from database.models import UserRole


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data.get("session")
        user = None

        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and session:
            operator = await get_operator_by_telegram_id(session, user.id)
            data["operator"] = operator
            data["is_supervisor"] = operator and operator.role in (
                UserRole.SUPERVISOR, UserRole.ADMIN
            )
            data["is_admin"] = operator and operator.role == UserRole.ADMIN

        return await handler(event, data)
