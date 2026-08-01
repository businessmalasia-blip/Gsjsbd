from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards.inline import admin_menu_kb, back_to_menu_kb, cancel_kb
from bot.states.forms import AdminForm, TrafficSourceForm
from database.crud import (
    get_all_operators, update_operator_role, get_operator_by_telegram_id,
    get_all_traffic_sources, create_traffic_source
)
from database.models import Operator, UserRole

router = Router()


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, operator: Operator, lang: str):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return
    await callback.message.edit_text(
        t("admin_title", lang),
        parse_mode="HTML",
        reply_markup=admin_menu_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:operators")
async def list_operators(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return

    operators = await get_all_operators(session)
    lines = [t("operators_list_title", lang)]
    for op in operators:
        username = f"@{op.username}" if op.username else "—"
        role = t(f"role_{op.role.value}", lang)
        lines.append(f"• {op.full_name} ({username}) — {role}")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:change_role")
async def start_change_role(
    callback: CallbackQuery, state: FSMContext, operator: Operator, lang: str
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return
    await callback.message.edit_text(
        t("enter_tg_id", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(AdminForm.operator_telegram_id)
    await callback.answer()


@router.message(AdminForm.operator_telegram_id)
async def process_operator_id(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer(t("invalid_tg_id", lang))
        return

    target = await get_operator_by_telegram_id(session, tg_id)
    if not target:
        await message.answer(t("operator_not_found", lang), reply_markup=back_to_menu_kb(lang))
        await state.clear()
        return

    await state.update_data(target_id=target.id)
    builder = InlineKeyboardBuilder()
    builder.button(text=t("role_operator", lang), callback_data="setrole:operator")
    builder.button(text=t("role_supervisor", lang), callback_data="setrole:supervisor")
    builder.button(text=t("cancel", lang), callback_data="menu:main")
    builder.adjust(2, 1)
    await message.answer(
        t("choose_role", lang, name=target.full_name),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AdminForm.new_role)


@router.callback_query(F.data.startswith("setrole:"), AdminForm.new_role)
async def process_role_change(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str
):
    role_str = callback.data.split(":")[1]
    role = UserRole(role_str)
    data = await state.get_data()
    await update_operator_role(session, data["target_id"], role)
    await state.clear()
    await callback.message.edit_text(
        t("role_changed", lang, role=t(f"role_{role_str}", lang)),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:sources")
async def manage_sources(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return
    sources = await get_all_traffic_sources(session)

    builder = InlineKeyboardBuilder()
    builder.button(text=t("add_source_btn", lang), callback_data="source_admin:add")
    builder.button(text=t("back", lang), callback_data="admin:menu")
    builder.adjust(1)

    if sources:
        lines = [t("sources_title", lang)]
        for s in sources:
            lines.append(f"• {s.name}")
        text = "\n".join(lines)
    else:
        text = t("sources_empty", lang)

    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "source_admin:add")
async def add_source(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.message.edit_text(
        t("enter_source_name", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(TrafficSourceForm.name)
    await callback.answer()


@router.message(TrafficSourceForm.name)
async def process_source_name(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    source = await create_traffic_source(session, message.text.strip())
    await state.clear()
    await message.answer(
        t("source_added", lang, name=source.name),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )
