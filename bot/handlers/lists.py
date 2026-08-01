from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards.inline import back_to_menu_kb
from database.crud import get_list_entries
from database.models import ListType

router = Router()

LIST_META = {
    "green": ("🟢", "Green List"),
    "white": ("⚪", "White List"),
    "black": ("🔴", "Black List"),
}


@router.callback_query(F.data.startswith("list:"))
async def show_list(callback: CallbackQuery, session: AsyncSession, lang: str):
    list_type_str = callback.data.split(":")[1]
    list_type = ListType(list_type_str)
    entries = await get_list_entries(session, list_type, limit=50)
    icon, name = LIST_META[list_type_str]
    none = t("none", lang)

    if not entries:
        await callback.message.edit_text(
            f"{icon} <b>{name}</b>\n\n{t('list_empty', lang)}",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(lang),
        )
        await callback.answer()
        return

    lines = [f"{icon} <b>{name}</b> ({len(entries)})\n"]
    for entry in entries[:30]:
        line = f"• {entry.client_phone or entry.client_contact or none}"
        if entry.reason:
            line += f" | {entry.reason[:30]}"
        lines.append(line)

    if len(entries) > 30:
        lines.append(f"\n... +{len(entries) - 30}")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )
    await callback.answer()
