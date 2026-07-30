from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import back_to_menu_kb
from database.crud import get_list_entries
from database.models import ListType

router = Router()

LIST_NAMES = {
    "green": ("🟢", "Green List"),
    "white": ("⚪", "White List"),
    "black": ("🔴", "Black List"),
}


@router.callback_query(F.data.startswith("list:"))
async def show_list(callback: CallbackQuery, session: AsyncSession):
    list_type_str = callback.data.split(":")[1]
    list_type = ListType(list_type_str)
    entries = await get_list_entries(session, list_type, limit=50)
    icon, name = LIST_NAMES[list_type_str]

    if not entries:
        await callback.message.edit_text(
            f"{icon} <b>{name}</b>\n\nСписок пуст.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    lines = [f"{icon} <b>{name}</b> ({len(entries)} записей)\n"]
    for entry in entries[:30]:
        line = f"• {entry.client_name or '—'}"
        if entry.client_phone:
            line += f" | {entry.client_phone}"
        if entry.reason:
            line += f" | {entry.reason[:30]}"
        lines.append(line)

    if len(entries) > 30:
        lines.append(f"\n... и ещё {len(entries) - 30} записей")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()
