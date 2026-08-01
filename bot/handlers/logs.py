from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards.inline import back_to_menu_kb
from database.crud import get_action_logs
from database.models import Operator, UserRole

router = Router()

ACTION_ICONS = {
    "ticket_created": "📋",
    "ticket_status_changed": "🔄",
    "payment_added": "💰",
    "cancellation_noted": "❌",
    "list_added": "📌",
    "list_removed": "🗑",
    "operator_registered": "👤",
    "ticket_updated": "✏️",
}


@router.callback_query(F.data == "log:view")
async def view_logs(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return

    logs = await get_action_logs(session, limit=30)
    if not logs:
        await callback.message.edit_text(
            t("log_empty", lang), reply_markup=back_to_menu_kb(lang)
        )
        await callback.answer()
        return

    lines = [t("log_title", lang)]
    for log in logs:
        op_name = log.operator.full_name[:12] if log.operator else "—"
        icon = ACTION_ICONS.get(log.action_type.value, "•")
        time_str = log.created_at.strftime("%d.%m %H:%M")
        details = (log.details or "")[:50]
        lines.append(f"[{time_str}] {icon} {op_name}\n  {details}")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )
    await callback.answer()
