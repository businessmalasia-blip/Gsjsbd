from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import back_to_menu_kb
from database.crud import get_action_logs
from database.models import Operator, UserRole

router = Router()

ACTION_LABELS = {
    "ticket_created": "📋 Создано",
    "ticket_status_changed": "🔄 Статус",
    "payment_added": "💰 Оплата",
    "cancellation_noted": "❌ Отмена",
    "list_added": "📌 В список",
    "list_removed": "🗑 Из списка",
    "operator_registered": "👤 Регистрация",
    "ticket_updated": "✏️ Изменено",
}


@router.callback_query(F.data == "log:view")
async def view_logs(
    callback: CallbackQuery, session: AsyncSession, operator: Operator
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    logs = await get_action_logs(session, limit=30)
    if not logs:
        await callback.message.edit_text(
            "Журнал действий пуст.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    lines = ["📜 <b>Журнал действий (последние 30)</b>\n"]
    for log in logs:
        op_name = log.operator.full_name[:15] if log.operator else "Система"
        action = ACTION_LABELS.get(log.action_type.value, log.action_type.value)
        time_str = log.created_at.strftime("%d.%m %H:%M")
        details = (log.details or "")[:50]
        lines.append(f"[{time_str}] {action} | {op_name}\n  {details}")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
