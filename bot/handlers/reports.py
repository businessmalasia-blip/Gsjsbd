from datetime import datetime, timedelta, date
import pytz
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import report_period_kb, back_to_menu_kb, cancel_kb
from bot.states.forms import ReportForm
from config import settings
from database.crud import (
    get_report_stats, get_operator_stats, get_traffic_source_stats,
    get_cancellation_reasons_stats
)
from database.models import Operator, UserRole

router = Router()


def get_tz():
    return pytz.timezone(settings.TIMEZONE)


def _period_bounds(period: str):
    tz = get_tz()
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return today_start, now
    elif period == "yesterday":
        yesterday = today_start - timedelta(days=1)
        return yesterday, today_start
    elif period == "week":
        return today_start - timedelta(days=7), now
    elif period == "month":
        return today_start - timedelta(days=30), now
    return None, None


@router.callback_query(F.data == "report:menu")
async def report_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📊 <b>Отчёты</b>\n\nВыберите период:",
        parse_mode="HTML",
        reply_markup=report_period_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("report:period:"))
async def report_by_period(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, operator: Operator
):
    period = callback.data.split("report:period:")[1]

    if period == "custom":
        await callback.message.edit_text(
            "📅 Введите начальную дату (ДД.ММ.ГГГГ):",
            reply_markup=cancel_kb(),
        )
        await state.set_state(ReportForm.date_from)
        await callback.answer()
        return

    date_from, date_to = _period_bounds(period)
    await _send_report(callback.message, session, date_from, date_to, operator, edit=True)
    await callback.answer()


@router.message(ReportForm.date_from)
async def process_date_from(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        tz = get_tz()
        dt = tz.localize(dt)
    except ValueError:
        await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ:")
        return
    await state.update_data(date_from=dt.isoformat())
    await message.answer("Введите конечную дату (ДД.ММ.ГГГГ):", reply_markup=cancel_kb())
    await state.set_state(ReportForm.date_to)


@router.message(ReportForm.date_to)
async def process_date_to(
    message: Message, state: FSMContext, session: AsyncSession, operator: Operator
):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        tz = get_tz()
        dt = tz.localize(dt).replace(hour=23, minute=59, second=59)
    except ValueError:
        await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ:")
        return

    data = await state.get_data()
    date_from = datetime.fromisoformat(data["date_from"])
    await state.clear()
    await _send_report(message, session, date_from, dt, operator)


async def _send_report(
    target, session: AsyncSession, date_from: datetime,
    date_to: datetime, operator: Operator, edit: bool = False
):
    is_supervisor = operator and operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    op_id = None if is_supervisor else (operator.id if operator else None)

    stats = await get_report_stats(session, date_from, date_to, op_id)
    s = stats["by_status"]

    period_str = (
        f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"
    )
    text = (
        f"📊 <b>Отчёт за период: {period_str}</b>\n\n"
        f"📋 Всего обращений: <b>{stats['total']}</b>\n"
        f"🆕 Новых: {s.get('new', 0)}\n"
        f"🔄 В работе: {s.get('in_progress', 0)}\n"
        f"✅ Оплачено: <b>{s.get('paid', 0)}</b>\n"
        f"❌ Отменено: {s.get('cancelled', 0)}\n"
        f"⏸ На паузе: {s.get('on_hold', 0)}\n\n"
        f"💰 Общая сумма оплат: <b>{stats['total_payment']:.2f} руб.</b>\n"
    )

    if is_supervisor:
        reasons = await get_cancellation_reasons_stats(session, date_from, date_to)
        if reasons:
            text += "\n❌ <b>Причины отмен:</b>\n"
            for r in reasons[:5]:
                text += f"  • {r['reason'][:40]}: {r['count']} раз\n"

    text += f"\n🕐 Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"

    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb())
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=back_to_menu_kb())


# ─── Operator Analytics (supervisor only) ────────────────────────────────────

@router.callback_query(F.data == "report:operators")
async def report_operators(
    callback: CallbackQuery, session: AsyncSession, operator: Operator
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    tz = get_tz()
    now = datetime.now(tz)
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    stats = await get_operator_stats(session, date_from, now)

    if not stats:
        await callback.message.edit_text(
            "Данных по операторам за последние 30 дней нет.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    lines = ["👥 <b>Аналитика операторов (30 дней)</b>\n"]
    for i, s in enumerate(stats, 1):
        conv_rate = (s["paid"] / s["total"] * 100) if s["total"] else 0
        lines.append(
            f"{i}. <b>{s['name']}</b>\n"
            f"   Обращений: {s['total']} | ✅ {s['paid']} | ❌ {s['cancelled']}\n"
            f"   Конверсия: {conv_rate:.1f}%"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


# ─── Traffic Source Analytics (supervisor only) ───────────────────────────────

@router.callback_query(F.data == "report:traffic")
async def report_traffic(
    callback: CallbackQuery, session: AsyncSession, operator: Operator
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    tz = get_tz()
    now = datetime.now(tz)
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    stats = await get_traffic_source_stats(session, date_from, now)

    if not stats:
        await callback.message.edit_text(
            "Данных по источникам трафика за последние 30 дней нет.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    lines = ["📈 <b>Аналитика трафика (30 дней)</b>\n"]
    for i, s in enumerate(stats, 1):
        lines.append(
            f"{i}. <b>{s['name']}</b>\n"
            f"   Обращений: {s['total']} | Выручка: {s['revenue']:.2f} руб."
        )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
