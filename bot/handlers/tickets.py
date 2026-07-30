from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import (
    ticket_status_kb, traffic_sources_kb, confirm_kb, cancel_kb,
    list_type_kb, back_to_menu_kb
)
from bot.states.forms import TicketForm, StatusChangeForm, PaymentForm, SearchForm
from database.crud import (
    create_ticket, get_ticket, update_ticket_status, add_payment,
    search_tickets, get_tickets_by_operator, get_all_traffic_sources,
    get_or_create_traffic_source, add_to_list
)
from database.models import Operator, TicketStatus, ListType

router = Router()

STATUS_LABELS = {
    "new": "🆕 Новый",
    "in_progress": "🔄 В работе",
    "paid": "✅ Оплачен",
    "cancelled": "❌ Отменён",
    "on_hold": "⏸ На паузе",
}


# ─── Create Ticket ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:new")
async def start_ticket(callback: CallbackQuery, state: FSMContext, operator: Operator | None):
    if not operator:
        await callback.answer("Необходима регистрация.", show_alert=True)
        return
    await callback.message.edit_text(
        "📋 <b>Новое обращение</b>\n\nВведите имя клиента:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TicketForm.client_name)
    await callback.answer()


@router.message(TicketForm.client_name)
async def process_client_name(message: Message, state: FSMContext):
    await state.update_data(client_name=message.text.strip())
    await message.answer(
        "📱 Введите номер телефона клиента (или нажмите /skip):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TicketForm.client_phone)


@router.message(TicketForm.client_phone)
async def process_client_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(client_phone=None if phone == "/skip" else phone)
    await message.answer(
        "💬 Введите контакт клиента (ник Telegram, email и т.д.) или /skip:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TicketForm.client_contact)


@router.message(TicketForm.client_contact)
async def process_client_contact(
    message: Message, state: FSMContext, session: AsyncSession
):
    contact = message.text.strip()
    await state.update_data(client_contact=None if contact == "/skip" else contact)
    sources = await get_all_traffic_sources(session)
    await message.answer(
        "📡 Выберите источник трафика:",
        reply_markup=traffic_sources_kb(sources),
    )
    await state.set_state(TicketForm.traffic_source)


@router.callback_query(F.data.startswith("source:"), TicketForm.traffic_source)
async def process_traffic_source(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
):
    data = callback.data.split(":")[1]
    if data == "skip":
        await state.update_data(traffic_source_id=None)
    elif data == "new":
        await callback.message.edit_text(
            "Введите название нового источника трафика:",
            reply_markup=cancel_kb(),
        )
        await state.set_state(TicketForm.traffic_source)
        await callback.answer()
        return
    else:
        await state.update_data(traffic_source_id=int(data))

    await callback.message.edit_text(
        "📝 Описание обращения (или /skip):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TicketForm.description)
    await callback.answer()


@router.message(TicketForm.traffic_source)
async def process_new_traffic_source(
    message: Message, state: FSMContext, session: AsyncSession
):
    source = await get_or_create_traffic_source(session, message.text.strip())
    await state.update_data(traffic_source_id=source.id)
    await message.answer(
        "📝 Описание обращения (или /skip):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(TicketForm.description)


@router.message(TicketForm.description)
async def process_description(message: Message, state: FSMContext):
    desc = message.text.strip()
    await state.update_data(description=None if desc == "/skip" else desc)
    data = await state.get_data()
    await message.answer(
        f"📋 <b>Подтвердите создание обращения:</b>\n\n"
        f"Клиент: <b>{data.get('client_name')}</b>\n"
        f"Телефон: {data.get('client_phone') or '—'}\n"
        f"Контакт: {data.get('client_contact') or '—'}\n"
        f"Описание: {data.get('description') or '—'}",
        parse_mode="HTML",
        reply_markup=confirm_kb("ticket_new"),
    )
    await state.set_state(TicketForm.confirm)


@router.callback_query(F.data == "ticket_new:confirm", TicketForm.confirm)
async def confirm_ticket_creation(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, operator: Operator
):
    data = await state.get_data()
    ticket = await create_ticket(
        session,
        operator_id=operator.id,
        client_name=data["client_name"],
        client_phone=data.get("client_phone"),
        client_contact=data.get("client_contact"),
        traffic_source_id=data.get("traffic_source_id"),
        description=data.get("description"),
    )
    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Обращение #{ticket.id} создано!</b>\n\n"
        f"Клиент: {ticket.client_name}\n"
        f"Статус: {STATUS_LABELS['new']}",
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value),
    )
    await callback.answer("Обращение создано!")


# ─── View Ticket ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ticket:view:"))
async def view_ticket(
    callback: CallbackQuery, session: AsyncSession, operator: Operator
):
    ticket_id = int(callback.data.split(":")[2])
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return

    payments_total = sum(p.amount for p in ticket.payments)
    source_name = ticket.traffic_source.name if ticket.traffic_source else "—"
    text = (
        f"📋 <b>Обращение #{ticket.id}</b>\n\n"
        f"Клиент: <b>{ticket.client_name}</b>\n"
        f"Телефон: {ticket.client_phone or '—'}\n"
        f"Контакт: {ticket.client_contact or '—'}\n"
        f"Статус: {STATUS_LABELS.get(ticket.status.value, ticket.status.value)}\n"
        f"Оператор: {ticket.operator.full_name}\n"
        f"Источник: {source_name}\n"
        f"Сумма оплат: <b>{payments_total} руб.</b>\n"
        f"Описание: {ticket.description or '—'}\n"
    )
    if ticket.cancellation_reason:
        text += f"Причина отмены: {ticket.cancellation_reason}\n"
    text += f"\nСоздан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value),
    )
    await callback.answer()


# ─── My Tickets ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:my")
async def my_tickets(
    callback: CallbackQuery, session: AsyncSession, operator: Operator
):
    if not operator:
        await callback.answer("Необходима регистрация.", show_alert=True)
        return
    tickets = await get_tickets_by_operator(session, operator.id, limit=15)
    if not tickets:
        await callback.message.edit_text(
            "У вас пока нет обращений.",
            reply_markup=back_to_menu_kb(),
        )
        await callback.answer()
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for t in tickets:
        status_icon = {"new": "🆕", "in_progress": "🔄", "paid": "✅",
                       "cancelled": "❌", "on_hold": "⏸"}.get(t.status.value, "📋")
        builder.button(
            text=f"{status_icon} #{t.id} {t.client_name[:20]}",
            callback_data=f"ticket:view:{t.id}",
        )
    builder.button(text="🔙 Назад", callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(
        f"📁 <b>Ваши обращения</b> ({len(tickets)}):",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


# ─── Change Status ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("status:"))
async def process_status_change(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, operator: Operator
):
    _, ticket_id_str, new_status_str = callback.data.split(":")
    ticket_id = int(ticket_id_str)
    new_status = TicketStatus(new_status_str)

    if new_status == TicketStatus.CANCELLED:
        await state.update_data(ticket_id=ticket_id, new_status=new_status_str)
        await callback.message.edit_text(
            "❌ Укажите причину отмены:",
            reply_markup=cancel_kb(),
        )
        await state.set_state(StatusChangeForm.cancellation_reason)
        await callback.answer()
        return

    ticket = await update_ticket_status(session, ticket_id, new_status, operator.id)
    if ticket:
        await callback.message.edit_text(
            f"✅ Статус обращения #{ticket_id} изменён на "
            f"<b>{STATUS_LABELS.get(new_status_str)}</b>",
            parse_mode="HTML",
            reply_markup=ticket_status_kb(ticket.id, ticket.status.value),
        )
    await callback.answer("Статус обновлён!")


@router.message(StatusChangeForm.cancellation_reason)
async def process_cancellation_reason(
    message: Message, state: FSMContext, session: AsyncSession, operator: Operator
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
            f"✅ Обращение #{ticket_id} отменено.\n"
            f"Причина: {ticket.cancellation_reason}",
            reply_markup=ticket_status_kb(ticket.id, ticket.status.value),
        )


# ─── Payment ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("payment:"))
async def start_payment(callback: CallbackQuery, state: FSMContext):
    ticket_id = int(callback.data.split(":")[1])
    await state.update_data(ticket_id=ticket_id)
    await callback.message.edit_text(
        f"💰 Введите сумму оплаты для обращения #{ticket_id} (в рублях):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(PaymentForm.amount)
    await callback.answer()


@router.message(PaymentForm.amount)
async def process_payment_amount(message: Message, state: FSMContext):
    try:
        amount = Decimal(message.text.strip().replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("Неверная сумма. Введите положительное число:")
        return
    await state.update_data(amount=str(amount))
    await message.answer(
        "💬 Комментарий к оплате (или /skip):",
        reply_markup=cancel_kb(),
    )
    await state.set_state(PaymentForm.comment)


@router.message(PaymentForm.comment)
async def process_payment_comment(
    message: Message, state: FSMContext, session: AsyncSession, operator: Operator
):
    data = await state.get_data()
    comment_text = message.text.strip()
    comment = None if comment_text == "/skip" else comment_text
    payment = await add_payment(
        session,
        ticket_id=data["ticket_id"],
        operator_id=operator.id,
        amount=Decimal(data["amount"]),
        comment=comment,
    )
    ticket = await get_ticket(session, data["ticket_id"])
    await state.clear()
    await message.answer(
        f"✅ <b>Оплата добавлена!</b>\n\n"
        f"Обращение: #{data['ticket_id']}\n"
        f"Сумма: <b>{payment.amount} руб.</b>\n"
        f"Комментарий: {comment or '—'}",
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value) if ticket else back_to_menu_kb(),
    )


# ─── Search ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "ticket:search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 Введите имя, телефон или контакт клиента для поиска:",
        reply_markup=cancel_kb(),
    )
    await state.set_state(SearchForm.query)
    await callback.answer()


@router.message(SearchForm.query)
async def process_search(
    message: Message, state: FSMContext, session: AsyncSession, operator: Operator
):
    query = message.text.strip()
    tickets = await search_tickets(session, query, limit=10)
    await state.clear()

    if not tickets:
        await message.answer(
            f"По запросу «{query}» ничего не найдено.",
            reply_markup=back_to_menu_kb(),
        )
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for t in tickets:
        status_icon = {"new": "🆕", "in_progress": "🔄", "paid": "✅",
                       "cancelled": "❌", "on_hold": "⏸"}.get(t.status.value, "📋")
        op_name = t.operator.full_name[:15] if t.operator else "—"
        builder.button(
            text=f"{status_icon} #{t.id} {t.client_name[:15]} ({op_name})",
            callback_data=f"ticket:view:{t.id}",
        )
    builder.button(text="🔙 Назад", callback_data="menu:main")
    builder.adjust(1)
    await message.answer(
        f"🔍 <b>Результаты поиска «{query}»</b> ({len(tickets)}):",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


# ─── Add to List ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("addlist:"))
async def add_to_list_menu(
    callback: CallbackQuery, session: AsyncSession
):
    ticket_id = int(callback.data.split(":")[1])
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return
    await callback.message.edit_text(
        f"📋 Добавить клиента по обращению #{ticket_id} в список:",
        reply_markup=list_type_kb(ticket_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("list_add:"))
async def confirm_list_add(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, operator: Operator
):
    parts = callback.data.split(":")
    ticket_id = int(parts[1])
    list_type_str = parts[2]
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        await callback.answer("Обращение не найдено.", show_alert=True)
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
    list_names = {"green": "Green List", "white": "White List", "black": "Black List"}
    await callback.message.edit_text(
        f"✅ Клиент <b>{ticket.client_name}</b> добавлен в "
        f"<b>{list_names[list_type_str]}</b>",
        parse_mode="HTML",
        reply_markup=ticket_status_kb(ticket.id, ticket.status.value),
    )
    await callback.answer()
