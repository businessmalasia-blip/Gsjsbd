from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards.inline import admin_menu_kb, back_to_menu_kb, cancel_kb
from bot.states.forms import AdminForm, TrafficSourceForm, ModelForm, MasterForm
from database.crud import (
    get_all_operators, update_operator_role, get_operator_by_telegram_id,
    get_all_traffic_sources, create_traffic_source,
    get_all_models, create_model,
    get_all_masters, create_master,
)
from database.models import Operator, UserRole

router = Router()


def _supervisor_check(operator: Operator) -> bool:
    return operator and operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, operator: Operator, lang: str):
    if not _supervisor_check(operator):
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
    if not _supervisor_check(operator):
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
    if not _supervisor_check(operator):
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


# ─── Traffic Sources ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:sources")
async def manage_sources(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not _supervisor_check(operator):
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


# ─── Models ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:models")
async def manage_models(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not _supervisor_check(operator):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return
    models = await get_all_models(session)

    builder = InlineKeyboardBuilder()
    builder.button(text=t("add_model", lang), callback_data="model_admin:add")
    builder.button(text=t("back", lang), callback_data="admin:menu")
    builder.adjust(1)

    if models:
        lines = [t("models_title", lang)]
        for m in models:
            lines.append(f"• {m.name}")
        text = "\n".join(lines)
    else:
        text = t("models_empty", lang)

    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "model_admin:add")
async def add_model(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.message.edit_text(
        t("enter_model_name", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(ModelForm.name)
    await callback.answer()


@router.message(ModelForm.name)
async def process_model_name(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    model = await create_model(session, message.text.strip())
    await state.clear()
    await message.answer(
        t("model_added", lang, name=model.name),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )


# ─── Masters ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:masters")
async def manage_masters(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    if not _supervisor_check(operator):
        await callback.answer(t("access_denied", lang), show_alert=True)
        return
    masters = await get_all_masters(session)

    builder = InlineKeyboardBuilder()
    builder.button(text=t("add_master", lang), callback_data="master_admin:add")
    builder.button(text=t("back", lang), callback_data="admin:menu")
    builder.adjust(1)

    if masters:
        lines = [t("masters_title", lang)]
        for m in masters:
            lines.append(f"• {m.name}")
        text = "\n".join(lines)
    else:
        text = t("masters_empty", lang)

    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "master_admin:add")
async def add_master(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.message.edit_text(
        t("enter_master_name", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(MasterForm.name)
    await callback.answer()


@router.message(MasterForm.name)
async def process_master_name(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    master = await create_master(session, message.text.strip())
    await state.clear()
    await message.answer(
        t("master_added", lang, name=master.name),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(lang),
    )
