from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t
from bot.keyboards.inline import main_menu_kb, cancel_kb
from bot.states.forms import RegistrationForm
from config import settings
from database.crud import create_operator, update_operator_language
from database.models import Operator, UserRole

router = Router()


def role_label(role: UserRole, lang: str) -> str:
    return {
        UserRole.OPERATOR: t("role_operator", lang),
        UserRole.SUPERVISOR: t("role_supervisor", lang),
        UserRole.ADMIN: t("role_admin", lang),
    }.get(role, role.value)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    operator: Operator | None,
    lang: str,
):
    await state.clear()
    if operator:
        is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
        await message.answer(
            t("welcome", lang, name=operator.full_name, role=role_label(operator.role, lang)),
            reply_markup=main_menu_kb(lang=lang, is_supervisor=is_sup),
            parse_mode="HTML",
        )
        return

    await message.answer(
        t("welcome_new", "ru"),
        reply_markup=cancel_kb("ru"),
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
        await message.answer(t("name_too_short", "ru"))
        return

    tg_id = message.from_user.id
    role = UserRole.ADMIN if tg_id in settings.admin_ids_list else UserRole.OPERATOR

    operator = await create_operator(
        session,
        telegram_id=tg_id,
        full_name=full_name,
        username=message.from_user.username,
        role=role,
        language="ru",
    )
    await state.clear()
    is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    await message.answer(
        t("reg_done", "ru", name=full_name, role=role_label(role, "ru")),
        reply_markup=main_menu_kb(lang="ru", is_supervisor=is_sup),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:main")
async def back_to_main(
    callback: CallbackQuery,
    state: FSMContext,
    operator: Operator | None,
    lang: str,
):
    await state.clear()
    if not operator:
        await callback.message.edit_text(t("need_registration", "ru"))
        return
    is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    await callback.message.edit_text(
        t("main_menu", lang, name=operator.full_name),
        reply_markup=main_menu_kb(lang=lang, is_supervisor=is_sup),
    )
    await callback.answer()


@router.callback_query(F.data == "lang:toggle")
async def toggle_language(
    callback: CallbackQuery,
    session: AsyncSession,
    operator: Operator | None,
    lang: str,
):
    if not operator:
        await callback.answer(t("need_registration", "ru"), show_alert=True)
        return
    new_lang = "en" if lang == "ru" else "ru"
    await update_operator_language(session, operator.id, new_lang)
    is_sup = operator.role in (UserRole.SUPERVISOR, UserRole.ADMIN)
    await callback.message.edit_text(
        t("main_menu", new_lang, name=operator.full_name),
        reply_markup=main_menu_kb(lang=new_lang, is_supervisor=is_sup),
    )
    await callback.answer(t("language_changed", new_lang))
