from datetime import datetime, timedelta
import pytz
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
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
async def report_menu(callback: CallbackQuery, lang: str):
    await callback.message.edit_text(
        t("report_menu", lang),
        parse_mode="HTML",
        reply_markup=report_period_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("report:period:"))
async def report_by_period(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    period = callback.data.split("report:period:")[1]
    if period == "custom":
        await callback.message.edit_text(
            t("enter_date_from", lang),
            reply_markup=cancel_kb(lang),
        )
        await state.set_state(ReportForm.date_from)
        await callback.answer()
        return

    date_from, date_to = _period_bounds(period)
    await _send_report(callback.message, session, date_from, date_to, operator, lang, edit=True)
    await callback.answer()


@router.message(ReportForm.date_from)
async def process_date_from(message: Message, state: FSMContext, lang: str):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        dt = get_tz().localize(dt)
    except ValueError:
        await message.answer(t("invalid_date", lang))
        return
    await state.update_data(date_from=dt.isoformat())
    await message.answer(t("enter_date_to", lang), reply_markup=cancel_kb(lang))
    await state.set_state(ReportForm.date_to)


@router.message(ReportForm.date_to)
async def process_date_to(
    message: Message, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        dt = get_tz().localize(dt).replace(hour=23, minute=59, second=59)
    except ValueError:
        await message.answer(t("invalid_date", lang))
        return
    data = await state.get_data()
    date_from = datetime.fromisoformat(data["date_from"])
    await state.clear()
    await _send_report(message, session, date_from, dt, operator, lang)


async def _send_report(
    target, session, date_from, date_to, operator: Operator, lang: str, edit: bool = False
):
    is_supervisor = operator and operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    op_id = None if is_supervisor else (operator.id if operator else None)
    stats = await get_report_stats(session, date_from, date_to, op_id)
    s = stats["by_status"]
    period_str = f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"

    lines = [
        f"📊 <b>{period_str}</b>\n",
        t("report_total", lang, total=stats["total"]),
        t("report_new", lang, v=s.get("new", 0)),
        t("report_in_progress", lang, v=s.get("in_progress", 0)),
        t("report_paid_count", lang, v=s.get("paid", 0)),
        t("report_cancelled", lang, v=s.get("cancelled", 0)),
        t("report_on_hold", lang, v=s.get("on_hold", 0)),
        "",
        t("report_amount", lang, amount=stats["total_payment"]),
    ]

    if is_supervisor:
        reasons = await get_cancellation_reasons_stats(session, date_from, date_to)
        if reasons:
            lines.append(t("cancel_reasons_title", lang))
            for r in reasons[:5]:
                lines.append(f"  • {r['reason'][:40]}: {r['count']}")

    lines.append(f"\n{t('report_generated', lang, time=datetime.now().strftime('%d.%m.%Y %H:%M'))}")
    text = "\n".join(lines)

    if edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=back_to_menu_kb(lang))
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=back_to_menu_kb(lang))


@router.callback_query(F.data == "report:operators")
async def report_operators(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return

    tz = get_tz()
    now = datetime.now(tz)
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    stats = await get_operator_stats(session, date_from, now)

    if not stats:
        await callback.message.edit_text(
            t("no_operator_data", lang), reply_markup=back_to_menu_kb(lang)
        )
        await callback.answer()
        return

    lines = [t("operator_analytics_title", lang)]
    for i, s in enumerate(stats, 1):
        conv = (s["paid"] / s["total"] * 100) if s["total"] else 0
        lines.append(
            f"{i}. <b>{s['name']}</b>\n"
            f"   {t('tickets', lang)}: {s['total']} | ✅ {s['paid']} | ❌ {s['cancelled']}\n"
            f"   {t('conversion', lang)}: {conv:.1f}%"
        )

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=back_to_menu_kb(lang)
    )
    await callback.answer()


@router.callback_query(F.data == "report:traffic")
async def report_traffic(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return

    tz = get_tz()
    now = datetime.now(tz)
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    stats = await get_traffic_source_stats(session, date_from, now)

    if not stats:
        await callback.message.edit_text(
            t("no_traffic_data", lang), reply_markup=back_to_menu_kb(lang)
        )
        await callback.answer()
        return

    lines = [t("traffic_analytics_title", lang)]
    for i, s in enumerate(stats, 1):
        lines.append(
            f"{i}. <b>{s['name']}</b>\n"
            f"   {t('tickets', lang)}: {s['total']} | {s['revenue']:.2f}"
        )

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=back_to_menu_kb(lang)
    )
    await callback.answer()
