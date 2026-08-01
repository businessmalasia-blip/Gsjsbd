from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_, or_, update, delete, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    Operator, Ticket, Payment, ClientList, ActionLog, TrafficSource,
    UserRole, TicketStatus, ListType, ActionType
)


# ─── Operators ────────────────────────────────────────────────────────────────

async def get_operator_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> Optional[Operator]:
    result = await session.execute(
        select(Operator).where(Operator.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def update_operator_language(
    session: AsyncSession, operator_id: int, language: str
) -> None:
    await session.execute(
        update(Operator).where(Operator.id == operator_id).values(language=language)
    )
    await session.commit()


async def create_operator(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None,
    role: UserRole = UserRole.OPERATOR,
    language: str = "ru",
) -> Operator:
    operator = Operator(
        telegram_id=telegram_id,
        full_name=full_name,
        username=username,
        role=role,
        language=language,
    )
    session.add(operator)
    await session.commit()
    await session.refresh(operator)
    await log_action(session, operator.id, None, ActionType.OPERATOR_REGISTERED,
                     f"Зарегистрирован оператор: {full_name}")
    return operator


async def get_all_operators(session: AsyncSession) -> List[Operator]:
    result = await session.execute(
        select(Operator).where(Operator.is_active == True).order_by(Operator.full_name)
    )
    return list(result.scalars().all())


async def update_operator_role(
    session: AsyncSession, operator_id: int, role: UserRole
) -> None:
    await session.execute(
        update(Operator).where(Operator.id == operator_id).values(role=role)
    )
    await session.commit()


# ─── Traffic Sources ───────────────────────────────────────────────────────────

async def get_all_traffic_sources(session: AsyncSession) -> List[TrafficSource]:
    result = await session.execute(
        select(TrafficSource).where(TrafficSource.is_active == True).order_by(TrafficSource.name)
    )
    return list(result.scalars().all())


async def create_traffic_source(session: AsyncSession, name: str) -> TrafficSource:
    source = TrafficSource(name=name)
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def get_or_create_traffic_source(
    session: AsyncSession, name: str
) -> TrafficSource:
    result = await session.execute(
        select(TrafficSource).where(TrafficSource.name == name)
    )
    source = result.scalar_one_or_none()
    if not source:
        source = await create_traffic_source(session, name)
    return source


# ─── Tickets ──────────────────────────────────────────────────────────────────

async def create_ticket(
    session: AsyncSession,
    operator_id: int,
    client_phone: Optional[str] = None,
    client_contact: Optional[str] = None,
    traffic_source_id: Optional[int] = None,
    description: Optional[str] = None,
    client_name: Optional[str] = None,
) -> Ticket:
    ticket = Ticket(
        operator_id=operator_id,
        client_name=client_name,
        client_phone=client_phone,
        client_contact=client_contact,
        traffic_source_id=traffic_source_id,
        description=description,
        status=TicketStatus.NEW,
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    await log_action(session, operator_id, ticket.id, ActionType.TICKET_CREATED,
                     f"Создано обращение #{ticket.id}: {client_phone or client_contact or '—'}")
    return ticket


async def get_ticket(session: AsyncSession, ticket_id: int) -> Optional[Ticket]:
    result = await session.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.operator),
            selectinload(Ticket.traffic_source),
            selectinload(Ticket.payments),
        )
        .where(Ticket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def update_ticket_status(
    session: AsyncSession,
    ticket_id: int,
    new_status: TicketStatus,
    operator_id: int,
    cancellation_reason: Optional[str] = None,
    departure_reason: Optional[str] = None,
) -> Optional[Ticket]:
    ticket = await get_ticket(session, ticket_id)
    if not ticket:
        return None
    old_status = ticket.status
    ticket.status = new_status
    if cancellation_reason:
        ticket.cancellation_reason = cancellation_reason
    if departure_reason:
        ticket.departure_reason = departure_reason
    if new_status in (TicketStatus.PAID, TicketStatus.CANCELLED, TicketStatus.DEPARTED):
        ticket.closed_at = datetime.utcnow()
    await session.commit()
    await session.refresh(ticket)
    reason_note = ""
    if cancellation_reason:
        reason_note = f". Причина отмены: {cancellation_reason}"
    elif departure_reason:
        reason_note = f". Причина ухода: {departure_reason}"
    await log_action(
        session, operator_id, ticket_id, ActionType.TICKET_STATUS_CHANGED,
        f"Статус #{ticket_id}: {old_status.value} → {new_status.value}{reason_note}"
    )
    return ticket


async def add_payment(
    session: AsyncSession,
    ticket_id: int,
    operator_id: int,
    amount: Decimal,
    comment: Optional[str] = None,
) -> Payment:
    payment = Payment(
        ticket_id=ticket_id,
        operator_id=operator_id,
        amount=amount,
        comment=comment,
    )
    session.add(payment)
    ticket = await get_ticket(session, ticket_id)
    if ticket:
        current = ticket.amount or Decimal("0")
        ticket.amount = current + amount
        if ticket.status == TicketStatus.NEW or ticket.status == TicketStatus.IN_PROGRESS:
            ticket.status = TicketStatus.PAID
    await session.commit()
    await session.refresh(payment)
    await log_action(session, operator_id, ticket_id, ActionType.PAYMENT_ADDED,
                     f"Оплата по обращению #{ticket_id}: {amount} руб.")
    return payment


async def search_tickets(
    session: AsyncSession,
    query: str,
    operator_id: Optional[int] = None,
    status: Optional[TicketStatus] = None,
    limit: int = 10,
) -> List[Ticket]:
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.operator), selectinload(Ticket.traffic_source))
        .where(
            or_(
                Ticket.client_name.ilike(f"%{query}%"),
                Ticket.client_phone.ilike(f"%{query}%"),
                Ticket.client_contact.ilike(f"%{query}%"),
            )
        )
    )
    if operator_id:
        stmt = stmt.where(Ticket.operator_id == operator_id)
    if status:
        stmt = stmt.where(Ticket.status == status)
    stmt = stmt.order_by(Ticket.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_tickets_by_operator(
    session: AsyncSession, operator_id: int, limit: int = 20
) -> List[Ticket]:
    result = await session.execute(
        select(Ticket)
        .options(selectinload(Ticket.traffic_source))
        .where(Ticket.operator_id == operator_id)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ─── Client Lists ─────────────────────────────────────────────────────────────

async def add_to_list(
    session: AsyncSession,
    list_type: ListType,
    added_by_id: int,
    client_name: Optional[str] = None,
    client_phone: Optional[str] = None,
    client_contact: Optional[str] = None,
    reason: Optional[str] = None,
    ticket_id: Optional[int] = None,
) -> ClientList:
    entry = ClientList(
        list_type=list_type,
        client_name=client_name,
        client_phone=client_phone,
        client_contact=client_contact,
        reason=reason,
        ticket_id=ticket_id,
        added_by_id=added_by_id,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    await log_action(
        session, added_by_id, ticket_id, ActionType.LIST_ADDED,
        f"Добавлен в {list_type.value.upper()} LIST: {client_name or client_phone}"
    )
    return entry


async def check_client_in_lists(
    session: AsyncSession, phone: str
) -> List[ClientList]:
    result = await session.execute(
        select(ClientList).where(ClientList.client_phone == phone)
    )
    return list(result.scalars().all())


async def get_list_entries(
    session: AsyncSession, list_type: ListType, limit: int = 50
) -> List[ClientList]:
    result = await session.execute(
        select(ClientList)
        .where(ClientList.list_type == list_type)
        .order_by(ClientList.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ─── Reports ──────────────────────────────────────────────────────────────────

async def get_report_stats(
    session: AsyncSession,
    date_from: datetime,
    date_to: datetime,
    operator_id: Optional[int] = None,
) -> dict:
    filters = [
        Ticket.created_at >= date_from,
        Ticket.created_at <= date_to,
    ]
    if operator_id:
        filters.append(Ticket.operator_id == operator_id)

    total_q = await session.execute(
        select(func.count(Ticket.id)).where(and_(*filters))
    )
    total = total_q.scalar() or 0

    by_status = {}
    for status in TicketStatus:
        q = await session.execute(
            select(func.count(Ticket.id)).where(and_(*filters, Ticket.status == status))
        )
        by_status[status.value] = q.scalar() or 0

    payment_q = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Ticket, Payment.ticket_id == Ticket.id)
        .where(and_(*filters))
    )
    total_payment = payment_q.scalar() or 0

    return {
        "total": total,
        "by_status": by_status,
        "total_payment": float(total_payment),
    }


async def get_operator_stats(
    session: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> List[dict]:
    filters = [Ticket.created_at >= date_from, Ticket.created_at <= date_to]

    result = await session.execute(
        select(
            Operator.full_name,
            func.count(Ticket.id).label("total"),
            func.sum(case((Ticket.status == TicketStatus.PAID, 1), else_=0)).label("paid"),
            func.sum(case((Ticket.status == TicketStatus.CANCELLED, 1), else_=0)).label("cancelled"),
            func.sum(case((Ticket.status == TicketStatus.DEPARTED, 1), else_=0)).label("departed"),
        )
        .join(Ticket, Ticket.operator_id == Operator.id)
        .where(and_(*filters))
        .group_by(Operator.id, Operator.full_name)
        .order_by(func.count(Ticket.id).desc())
    )
    rows = result.all()
    return [
        {
            "name": r.full_name,
            "total": r.total,
            "paid": r.paid or 0,
            "cancelled": r.cancelled or 0,
            "departed": r.departed or 0,
        }
        for r in rows
    ]


async def get_traffic_source_stats(
    session: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> List[dict]:
    filters = [Ticket.created_at >= date_from, Ticket.created_at <= date_to]

    result = await session.execute(
        select(
            TrafficSource.name,
            func.count(Ticket.id).label("total"),
            func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
        )
        .join(Ticket, Ticket.traffic_source_id == TrafficSource.id)
        .outerjoin(Payment, Payment.ticket_id == Ticket.id)
        .where(and_(*filters))
        .group_by(TrafficSource.id, TrafficSource.name)
        .order_by(func.count(Ticket.id).desc())
    )
    rows = result.all()
    return [
        {"name": r.name, "total": r.total, "revenue": float(r.revenue)}
        for r in rows
    ]


async def get_cancellation_reasons_stats(
    session: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> List[dict]:
    result = await session.execute(
        select(Ticket.cancellation_reason, func.count(Ticket.id).label("count"))
        .where(and_(
            Ticket.created_at >= date_from,
            Ticket.created_at <= date_to,
            Ticket.status == TicketStatus.CANCELLED,
            Ticket.cancellation_reason.isnot(None),
        ))
        .group_by(Ticket.cancellation_reason)
        .order_by(func.count(Ticket.id).desc())
    )
    return [{"reason": r.cancellation_reason, "count": r.count} for r in result.all()]


async def get_departure_reasons_stats(
    session: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> List[dict]:
    result = await session.execute(
        select(Ticket.departure_reason, func.count(Ticket.id).label("count"))
        .where(and_(
            Ticket.created_at >= date_from,
            Ticket.created_at <= date_to,
            Ticket.status == TicketStatus.DEPARTED,
            Ticket.departure_reason.isnot(None),
        ))
        .group_by(Ticket.departure_reason)
        .order_by(func.count(Ticket.id).desc())
    )
    return [{"reason": r.departure_reason, "count": r.count} for r in result.all()]


# ─── Action Log ───────────────────────────────────────────────────────────────

async def log_action(
    session: AsyncSession,
    operator_id: Optional[int],
    ticket_id: Optional[int],
    action_type: ActionType,
    details: str,
) -> None:
    log = ActionLog(
        operator_id=operator_id,
        ticket_id=ticket_id,
        action_type=action_type,
        details=details,
    )
    session.add(log)
    await session.commit()


async def get_action_logs(
    session: AsyncSession,
    ticket_id: Optional[int] = None,
    operator_id: Optional[int] = None,
    limit: int = 50,
) -> List[ActionLog]:
    stmt = (
        select(ActionLog)
        .options(selectinload(ActionLog.operator))
        .order_by(ActionLog.created_at.desc())
        .limit(limit)
    )
    if ticket_id:
        stmt = stmt.where(ActionLog.ticket_id == ticket_id)
    if operator_id:
        stmt = stmt.where(ActionLog.operator_id == operator_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())
