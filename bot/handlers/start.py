from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import main_menu_kb, cancel_kb
from bot.states.forms import RegistrationForm
from config import settings
from database.crud import create_operator, get_operator_by_telegram_id
from database.models import Operator, UserRole

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    operator: Operator | None,
):
    await state.clear()
    if operator:
        is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
        await message.answer(
            f"Добро пожаловать, {operator.full_name}!\n"
            f"Ваша роль: <b>{_role_label(operator.role)}</b>",
            reply_markup=main_menu_kb(is_supervisor=is_sup),
            parse_mode="HTML",
        )
        return

    # New operator — check if first user (auto-admin)
    await message.answer(
        "Добро пожаловать в CRM-систему чат-центра!\n\n"
        "Для регистрации введите ваше полное имя:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(RegistrationForm.full_name)


@router.message(RegistrationForm.full_name)
async def process_full_name(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
):
    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer("Имя слишком короткое. Введите ещё раз:")
        return

    tg_id = message.from_user.id
    role = UserRole.ADMIN if tg_id in settings.admin_ids_list else UserRole.OPERATOR

    operator = await create_operator(
        session,
        telegram_id=tg_id,
        full_name=full_name,
        username=message.from_user.username,
        role=role,
    )
    await state.clear()
    is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    await message.answer(
        f"Регистрация завершена!\n"
        f"Имя: <b>{full_name}</b>\n"
        f"Роль: <b>{_role_label(role)}</b>",
        reply_markup=main_menu_kb(is_supervisor=is_sup),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:main")
async def back_to_main(
    callback: CallbackQuery,
    state: FSMContext,
    operator: Operator | None,
):
    await state.clear()
    if not operator:
        await callback.message.edit_text("Используйте /start для регистрации.")
        return
    is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    await callback.message.edit_text(
        f"Главное меню | {operator.full_name}",
        reply_markup=main_menu_kb(is_supervisor=is_sup),
    )
    await callback.answer()


def _role_label(role: UserRole) -> str:
    return {
        UserRole.OPERATOR: "Оператор",
        UserRole.SUPERVISOR: "Руководитель",
        UserRole.ADMIN: "Администратор",
    }.get(role, role.value)
