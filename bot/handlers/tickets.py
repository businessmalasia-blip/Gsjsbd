from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.i18n import t, status_label
from bot.keyboards.inline import (
    ticket_status_kb, traffic_sources_kb, confirm_kb, cancel_kb,
    list_type_kb, back_to_menu_kb, models_kb, masters_kb,
    payment_type_kb, result_category_kb
)
from bot.states.forms import TicketForm, StatusChangeForm, PaymentForm, SearchForm
from database.crud import (
    create_ticket, get_ticket, update_ticket_status, add_payment,
    search_tickets, get_tickets_by_operator, get_all_traffic_sources,
    get_or_create_traffic_source, add_to_list, get_all_models,
    get_or_create_model, get_all_masters, get_or_create_master,
    set_ticket_result
)
from database.models import Operator, TicketStatus, ListType, PaymentType, ResultCategory

router = Router()

LIST_NAMES = {
    "green": ("🟢", "Green List"),
    "white": ("⚪", "White List"),
    "black": ("🔴", "Black List"),
}

RESULT_LABELS = {
    "positive_lead": "result_positive_lead_label",
    "booking": "result_booking_label",
    "general_lead": "result_general_lead_label",
}

CLIENT_STATUS_LABELS = {
    "new": "client_status_new",
    "white_list": "client_status_white_list",
    "black_list": "client_status_black_list",
}

PAYMENT_TYPE_LABELS = {
    "session": "payment_type_session",
    "cancellation": "payment_type_cancellation",
    "service": "payment_type_service",
    "extra_time": "payment_type_extra_time",
}


def format_ticket(ticket, lang: str) -> str:
    none = t("none", lang)
    rub = t("rub", lang)
    min_abbr = t("minutes_abbr", lang)

    # group payments by type
    pay_by_type: dict = {}
    extra_mins = 0
    for p in ticket.payments:
        ptype = p.payment_type.value
        pay_by_type[ptype] = pay_by_type.get(ptype, Decimal("0")) + p.amount
        if ptype == "extra_time" and p.extra_time_minutes:
            extra_mins += p.extra_time_minutes

    model_name = ticket.model.name if ticket.model else none
    master_name = ticket.master.name if ticket.master else none
    source_name = ticket.traffic_source.name if ticket.traffic_source else none
    client_status_key = CLIENT_STATUS_LABELS.get(
        ticket.client_status.value if ticket.client_status else "new", "client_status_new"
    )
    duration_str = f"{ticket.session_duration} {min_abbr}" if ticket.session_duration else none
    result_str = t(RESULT_LABELS.get(
        ticket.result_category.value if ticket.result_category else "", "none"
    ), lang) if ticket.result_category else none

    text = (
        f"📋 <b>#{ticket.id}</b>\n\n"
        f"{t('ticket_phone', lang)}: {ticket.client_phone or none}\n"
        f"{t('ticket_contact', lang)}: {ticket.client_contact or none}\n"
        f"{t('ticket_client_status', lang)}: {t(client_status_key, lang)}\n"
        f"{t('ticket_status', lang)}: {status_label(ticket.status.value, lang)}\n"
        f"{t('ticket_result', lang)}: {result_str}\n"
        f"{t('ticket_model', lang)}: {model_name}\n"
        f"{t('ticket_master', lang)}: {master_name}\n"
        f"{t('ticket_source', lang)}: {source_name}\n"
        f"{t('ticket_duration', lang)}: {duration_str}\n"
        f"{t('ticket_operator', lang)}: {ticket.operator.full_name}\n"
    )
    if pay_by_type:
        text += "\n"
        for ptype, amount in pay_by_type.items():
            label = t(PAYMENT_TYPE_LABELS.get(ptype, ptype), lang)
            text += f"  {label}: <b>{amount} {rub}</b>\n"
        if extra_mins:
            text += f"  {t('ticket_duration', lang)} (доп.): {extra_mins} {min_abbr}\n"
    if ticket.description:
        text += f"\n{t('ticket_description', lang)}: {ticket.description}\n"
    if ticket.cancellation_reason:
        text += f"{t('ticket_cancel_reason', lang)}: {ticket.cancellation_reason}\n"
    if ticket.departure_reason:
        text += f"{t('ticket_departure_reason', lang)}: {ticket.departure_reason}\n"
    text += f"\n{t('ticket_created_at', lang)}: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}"
    return text


# ─── Create Ticket ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:new")
async def start_ticket(callback: CallbackQuery, state: FSMContext, operator: Operator | None, lang: str):
    if not operator:
        await callback.answer(t("need_registration", lang), show_alert=True)
        return
    await callback.message.edit_text(
        t("new_ticket_title", lang),
        parse_mode="HTML",
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(TicketForm.client_phone)
    await callback.answer()


@router.message(TicketForm.client_phone)
async def process_client_phone(message: Message, state: FSMContext, lang: str):
    phone = message.text.strip()
    await state.update_data(client_phone=None if phone == "/skip" else phone)
    await message.answer(t("enter_contact", lang), reply_markup=cancel_kb(lang))
    await state.set_state(TicketForm.client_contact)


@router.message(TicketForm.client_contact)
async def process_client_contact(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    contact = message.text.strip()
    await state.update_data(client_contact=None if contact == "/skip" else contact)
    sources = await get_all_traffic_sources(session)
    await message.answer(
        t("choose_source", lang),
        reply_markup=traffic_sources_kb(sources, lang),
    )
    await state.set_state(TicketForm.traffic_source)


@router.callback_query(F.data.startswith("source:"), TicketForm.traffic_source)
async def process_traffic_source(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str
):
    data = callback.data.split(":")[1]
    if data == "skip":
        await state.update_data(traffic_source_id=None)
    elif data == "new":
        await callback.message.edit_text(
            t("enter_source_name", lang),
            reply_markup=cancel_kb(lang),
        )
        await state.set_state(TicketForm.traffic_source)
        await callback.answer()
        return
    else:
        await state.update_data(traffic_source_id=int(data))

    models = await get_all_models(session)
    await callback.message.edit_text(
        t("choose_model", lang),
        reply_markup=models_kb(models, lang),
    )
    await state.set_state(TicketForm.model_id)
    await callback.answer()


@router.message(TicketForm.traffic_source)
async def process_new_traffic_source(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    source = await get_or_create_traffic_source(session, message.text.strip())
    await state.update_data(traffic_source_id=source.id)
    models = await get_all_models(session)
    await message.answer(t("choose_model", lang), reply_markup=models_kb(models, lang))
    await state.set_state(TicketForm.model_id)


@router.callback_query(F.data.startswith("model:"), TicketForm.model_id)
async def process_model_selection(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str
):
    data = callback.data.split(":")[1]
    if data == "skip":
        await state.update_data(model_id=None)
    elif data == "new":
        await callback.message.edit_text(t("enter_model_name", lang), reply_markup=cancel_kb(lang))
        await callback.answer()
        return
    else:
        await state.update_data(model_id=int(data))

    masters = await get_all_masters(session)
    await callback.message.edit_text(
        t("choose_master", lang),
        reply_markup=masters_kb(masters, lang),
    )
    await state.set_state(TicketForm.master_id)
    await callback.answer()


@router.message(TicketForm.model_id)
async def process_new_model(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    m = await get_or_create_model(session, message.text.strip())
    await state.update_data(model_id=m.id)
    masters = await get_all_masters(session)
    await message.answer(t("choose_master", lang), reply_markup=masters_kb(masters, lang))
    await state.set_state(TicketForm.master_id)


@router.callback_query(F.data.startswith("master:"), TicketForm.master_id)
async def process_master_selection(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str
):
    data = callback.data.split(":")[1]
    if data == "skip":
        await state.update_data(master_id=None)
    elif data == "new":
        await callback.message.edit_text(t("enter_master_name", lang), reply_markup=cancel_kb(lang))
        await callback.answer()
        return
    else:
        await state.update_data(master_id=int(data))

    await callback.message.edit_text(
        t("enter_session_duration", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(TicketForm.session_duration)
    await callback.answer()


@router.message(TicketForm.master_id)
async def process_new_master(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    m = await get_or_create_master(session, message.text.strip())
    await state.update_data(master_id=m.id)
    await message.answer(t("enter_session_duration", lang), reply_markup=cancel_kb(lang))
    await state.set_state(TicketForm.session_duration)


@router.message(TicketForm.session_duration)
async def process_session_duration(message: Message, state: FSMContext, lang: str):
    text = message.text.strip()
    if text == "/skip":
        await state.update_data(session_duration=None)
    else:
        try:
            mins = int(text)
            if mins <= 0:
                raise ValueError
            await state.update_data(session_duration=mins)
        except ValueError:
            await message.answer(t("invalid_duration", lang))
            return
    await message.answer(t("enter_description", lang), reply_markup=cancel_kb(lang))
    await state.set_state(TicketForm.description)


@router.message(TicketForm.description)
async def process_description(message: Message, state: FSMContext, lang: str):
    desc = message.text.strip()
    await state.update_data(description=None if desc == "/skip" else desc)
    data = await state.get_data()
    none = t("none", lang)
    await message.answer(
        t("confirm_ticket", lang,
          phone=data.get("client_phone") or none,
          contact=data.get("client_contact") or none,
          description=data.get("description") or none),
        parse_mode="HTML",
        reply_markup=confirm_kb("ticket_new", lang),
    )
    await state.set_state(TicketForm.confirm)


@router.callback_query(F.data == "ticket_new:confirm", TicketForm.confirm)
async def confirm_ticket_creation(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    data = await state.get_data()
    ticket = await create_ticket(
        session,
        operator_id=operator.id,
        client_phone=data.get("client_phone"),
        client_contact=data.get("client_contact"),
        traffic_source_id=data.get("traffic_source_id"),
        description=data.get("description"),
        model_id=data.get("model_id"),
        master_id=data.get("master_id"),
        session_duration=data.get("session_duration"),
    )
    await state.clear()
    await callback.message.edit_text(
        t("ticket_created", lang, id=ticket.id, status=status_label("new", lang)),
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
    )
    await callback.answer()


# ─── View Ticket ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ticket:view:"))
async def view_ticket(
    callback: CallbackQuery, session: AsyncSession, lang: str
):
    ticket_id = int(callback.data.split(":")[2])
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        await callback.answer(t("ticket_not_found", lang), show_alert=True)
        return
    await callback.message.edit_text(
        format_ticket(ticket, lang),
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
    )
    await callback.answer()


# ─── My Tickets ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:my")
async def my_tickets(
    callback: CallbackQuery, session: AsyncSession, operator: Operator | None, lang: str
):
    if not operator:
        await callback.answer(t("need_registration", lang), show_alert=True)
        return
    tickets = await get_tickets_by_operator(session, operator.id, limit=15)
    if not tickets:
        await callback.message.edit_text(
            t("no_tickets", lang),
            reply_markup=back_to_menu_kb(lang),
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    icons = {
        "new": "🆕", "in_progress": "🔄", "paid": "✅",
        "cancelled": "❌", "on_hold": "⏸", "departed": "🚪"
    }
    for ticket in tickets:
        icon = icons.get(ticket.status.value, "📋")
        label = ticket.client_phone or ticket.client_contact or f"#{ticket.id}"
        builder.button(
            text=f"{icon} #{ticket.id} {label[:20]}",
            callback_data=f"ticket:view:{ticket.id}",
        )
    builder.button(text=t("home", lang), callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(
        t("my_tickets_title", lang, count=len(tickets)),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


# ─── Change Status ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("status:"))
async def process_status_change(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    _, ticket_id_str, new_status_str = callback.data.split(":")
    ticket_id = int(ticket_id_str)
    new_status = TicketStatus(new_status_str)

    if new_status == TicketStatus.CANCELLED:
        await state.update_data(ticket_id=ticket_id, new_status=new_status_str)
        await callback.message.edit_text(
            t("enter_cancel_reason", lang),
            reply_markup=cancel_kb(lang),
        )
        await state.set_state(StatusChangeForm.cancellation_reason)
        await callback.answer()
        return

    if new_status == TicketStatus.DEPARTED:
        await state.update_data(ticket_id=ticket_id, new_status=new_status_str)
        await callback.message.edit_text(
            t("enter_departure_reason", lang),
            reply_markup=cancel_kb(lang),
        )
        await state.set_state(StatusChangeForm.departure_reason)
        await callback.answer()
        return

    ticket = await update_ticket_status(session, ticket_id, new_status, operator.id)
    if ticket:
        await callback.message.edit_text(
            t("status_changed", lang, id=ticket_id, status=status_label(new_status_str, lang)),
            parse_mode="HTML",
            reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
        )
    await callback.answer(t("status_updated", lang))


@router.message(StatusChangeForm.cancellation_reason)
async def process_cancellation_reason(
    message: Message, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    new_status = TicketStatus(data["new_status"])
    ticket = await update_ticket_status(
        session, ticket_id, new_status, operator.id,
        cancellation_reason=message.text.strip()
    )
    await state.clear()
    if ticket:
        await message.answer(
            t("cancel_reason_done", lang, id=ticket_id, reason=ticket.cancellation_reason),
            reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
        )


@router.message(StatusChangeForm.departure_reason)
async def process_departure_reason(
    message: Message, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    new_status = TicketStatus(data["new_status"])
    ticket = await update_ticket_status(
        session, ticket_id, new_status, operator.id,
        departure_reason=message.text.strip()
    )
    await state.clear()
    if ticket:
        await message.answer(
            t("departure_reason_done", lang, id=ticket_id, reason=ticket.departure_reason),
            reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
        )


# ─── Set Result ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("result:"))
async def start_set_result(callback: CallbackQuery, lang: str):
    ticket_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        t("choose_result", lang, id=ticket_id),
        reply_markup=result_category_kb(ticket_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setresult:"))
async def confirm_set_result(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    result_value = parts[2]
    result = ResultCategory(result_value)
    ticket = await set_ticket_result(session, ticket_id, result, operator.id)
    if ticket:
        result_label = t(RESULT_LABELS.get(result_value, "none"), lang)
        await callback.message.edit_text(
            t("result_set", lang, result=result_label),
            parse_mode="HTML",
            reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
        )
    await callback.answer()


# ─── Payment ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("payment:"))
async def start_payment(callback: CallbackQuery, state: FSMContext, lang: str):
    ticket_id = int(callback.data.split(":")[1])
    await state.update_data(ticket_id=ticket_id)
    await callback.message.edit_text(
        t("choose_payment_type", lang, id=ticket_id),
        reply_markup=payment_type_kb(ticket_id, lang),
    )
    await state.set_state(PaymentForm.payment_type)
    await callback.answer()


@router.callback_query(F.data.startswith("paytype:"), PaymentForm.payment_type)
async def process_payment_type(
    callback: CallbackQuery, state: FSMContext, lang: str
):
    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    ptype = parts[2]
    await state.update_data(payment_type=ptype)

    if ptype == "extra_time":
        await callback.message.edit_text(
            t("enter_extra_minutes", lang),
            reply_markup=cancel_kb(lang),
        )
        await state.set_state(PaymentForm.extra_time_minutes)
    else:
        await state.update_data(extra_time_minutes=None)
        await callback.message.edit_text(
            t("enter_amount", lang, id=ticket_id),
            reply_markup=cancel_kb(lang),
        )
        await state.set_state(PaymentForm.amount)
    await callback.answer()


@router.message(PaymentForm.extra_time_minutes)
async def process_extra_minutes(message: Message, state: FSMContext, lang: str):
    try:
        mins = int(message.text.strip())
        if mins <= 0:
            raise ValueError
    except ValueError:
        await message.answer(t("invalid_minutes", lang))
        return
    data = await state.get_data()
    await state.update_data(extra_time_minutes=mins)
    await message.answer(
        t("enter_amount", lang, id=data["ticket_id"]),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(PaymentForm.amount)


@router.message(PaymentForm.amount)
async def process_payment_amount(message: Message, state: FSMContext, lang: str):
    try:
        amount = Decimal(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer(t("invalid_amount", lang))
        return
    await state.update_data(amount=str(amount))
    await message.answer(t("enter_comment", lang), reply_markup=cancel_kb(lang))
    await state.set_state(PaymentForm.comment)


@router.message(PaymentForm.comment)
async def process_payment_comment(
    message: Message, state: FSMContext, session: AsyncSession,
    operator: Operator, lang: str
):
    data = await state.get_data()
    comment_text = message.text.strip()
    comment = None if comment_text == "/skip" else comment_text
    ptype = PaymentType(data.get("payment_type", "session"))
    payment = await add_payment(
        session,
        ticket_id=data["ticket_id"],
        operator_id=operator.id,
        amount=Decimal(data["amount"]),
        payment_type=ptype,
        extra_time_minutes=data.get("extra_time_minutes"),
        comment=comment,
    )
    ticket = await get_ticket(session, data["ticket_id"])
    await state.clear()
    none = t("none", lang)
    type_label = t(PAYMENT_TYPE_LABELS.get(ptype.value, ptype.value), lang)
    await message.answer(
        t("payment_added", lang,
          id=data["ticket_id"],
          amount=payment.amount,
          comment=f"[{type_label}] {comment or none}"),
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang) if ticket else back_to_menu_kb(lang),
    )


# ─── Search ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:search")
async def start_search(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.message.edit_text(
        t("search_prompt", lang),
        reply_markup=cancel_kb(lang),
    )
    await state.set_state(SearchForm.query)
    await callback.answer()


@router.message(SearchForm.query)
async def process_search(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    query = message.text.strip()
    tickets = await search_tickets(session, query, limit=10)
    await state.clear()

    if not tickets:
        await message.answer(
            t("search_no_results", lang, query=query),
            reply_markup=back_to_menu_kb(lang),
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    icons = {
        "new": "🆕", "in_progress": "🔄", "paid": "✅",
        "cancelled": "❌", "on_hold": "⏸", "departed": "🚪"
    }
    for ticket in tickets:
        icon = icons.get(ticket.status.value, "📋")
        label = ticket.client_phone or ticket.client_contact or f"#{ticket.id}"
        op_name = ticket.operator.full_name[:12] if ticket.operator else "—"
        builder.button(
            text=f"{icon} #{ticket.id} {label[:15]} ({op_name})",
            callback_data=f"ticket:view:{ticket.id}",
        )
    builder.button(text=t("home", lang), callback_data="menu:main")
    builder.adjust(1)
    await message.answer(
        t("search_results", lang, query=query, count=len(tickets)),
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


# ─── Add to List ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("addlist:"))
async def add_to_list_menu(
    callback: CallbackQuery, session: AsyncSession, lang: str
):
    ticket_id = int(callback.data.split(":")[1])
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        await callback.answer(t("ticket_not_found", lang), show_alert=True)
        return
    await callback.message.edit_text(
        t("add_to_list", lang, id=ticket_id),
        reply_markup=list_type_kb(ticket_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("list_add:"))
async def confirm_list_add(
    callback: CallbackQuery, session: AsyncSession, operator: Operator, lang: str
):
    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    list_type_str = parts[2]
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        await callback.answer(t("ticket_not_found", lang), show_alert=True)
        return

    list_type = ListType(list_type_str)
    await add_to_list(
        session,
        list_type=list_type,
        added_by_id=operator.id,
        client_name=ticket.client_name,
        client_phone=ticket.client_phone,
        client_contact=ticket.client_contact,
        ticket_id=ticket_id,
    )
    _, list_name = LIST_NAMES[list_type_str]
    await callback.message.edit_text(
        t("added_to_list", lang, list_name=list_name),
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value, lang),
    )
    await callback.answer()
