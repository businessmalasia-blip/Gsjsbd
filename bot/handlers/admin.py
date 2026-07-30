from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import admin_menu_kb, back_to_menu_kb, cancel_kb
from bot.states.forms import AdminForm, TrafficSourceForm
from database.crud import (
    get_all_operators, update_operator_role, get_operator_by_telegram_id,
    get_all_traffic_sources, create_traffic_source
)
from database.models import Operator, UserRole

router = Router()


@router.callback_query(F.data == "admin:menu")
async def admin_menu(callback: CallbackQuery, operator: Operator):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ <b>Управление системой</b>",
        parse_mode="HTML",
        reply_markup=admin_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:operators")
async def list_operators(
    callback: CallbackQuery, session: AsyncSession, operator: Operator
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return

    operators = await get_all_operators(session)
    role_labels = {
        UserRole.OPERATOR: "Оператор",
        UserRole.SUPERVISOR: "Руководитель",
        UserRole.ADMIN: "Администратор",
    }
    lines = ["👥 <b>Список операторов</b>\n"]
    for op in operators:
        username = f"@{op.username}" if op.username else "—"
        lines.append(f"• {op.full_name} ({username}) — {role_labels[op.role]}")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:change_role")
async def start_change_role(
    callback: CallbackQuery, state: FSMContext, operator: Operator
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    await callback.message.edit_text(
        "Введите Telegram ID оператора для изменения роли:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AdminForm.operator_telegram_id)
    await callback.answer()


@router.message(AdminForm.operator_telegram_id)
async def process_operator_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат. Введите числовой Telegram ID:")
        return

    target = await get_operator_by_telegram_id(session, tg_id)
    if not target:
        await message.answer("Оператор не найден.", reply_markup=back_to_menu_kb())
        await state.clear()
        return

    await state.update_data(target_id=target.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Оператор", callback_data="setrole:operator")
    builder.button(text="👔 Руководитель", callback_data="setrole:supervisor")
    builder.button(text="🔙 Отмена", callback_data="menu:main")
    builder.adjust(2, 1)
    await message.answer(
        f"Выберите роль для <b>{target.full_name}</b>:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(AdminForm.new_role)


@router.callback_query(F.data.startswith("setrole:"), AdminForm.new_role)
async def process_role_change(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    role_str = callback.data.split(":")[1]
    role = UserRole(role_str)
    data = await state.get_data()
    await update_operator_role(session, data["target_id"], role)
    await state.clear()
    role_labels = {"operator": "Оператор", "supervisor": "Руководитель"}
    await callback.message.edit_text(
        f"✅ Роль изменена на <b>{role_labels.get(role_str, role_str)}</b>",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:sources")
async def manage_sources(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, operator: Operator
):
    if not operator or operator.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    sources = await get_all_traffic_sources(session)
    lines = ["📡 <b>Источники трафика</b>\n"]
    for s in sources:
        lines.append(f"• {s.name}")

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить источник", callback_data="source_admin:add")
    builder.button(text="🔙 Назад", callback_data="admin:menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "\n".join(lines) if sources else "📡 Источники трафика\n\nСписок пуст.",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "source_admin:add")
async def add_source(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите название нового источника трафика:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TrafficSourceForm.name)
    await callback.answer()


@router.message(TrafficSourceForm.name)
async def process_source_name(
    message: Message, state: FSMContext, session: AsyncSession
):
    name = message.text.strip()
    source = await create_traffic_source(session, name)
    await state.clear()
    await message.answer(
        f"✅ Источник трафика <b>{source.name}</b> добавлен.",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
