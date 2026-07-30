from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Text, Numeric, DateTime, Boolean,
    ForeignKey, Enum, Integer, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(PyEnum):
    OPERATOR = "operator"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class TicketStatus(PyEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    PAID = "paid"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class ListType(PyEnum):
    GREEN = "green"
    WHITE = "white"
    BLACK = "black"


class ActionType(PyEnum):
    TICKET_CREATED = "ticket_created"
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    PAYMENT_ADDED = "payment_added"
    CANCELLATION_NOTED = "cancellation_noted"
    LIST_ADDED = "list_added"
    LIST_REMOVED = "list_removed"
    OPERATOR_REGISTERED = "operator_registered"
    TICKET_UPDATED = "ticket_updated"


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.OPERATOR, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tickets: Mapped[List["Ticket"]] = relationship(back_populates="operator")
    action_logs: Mapped[List["ActionLog"]] = relationship(back_populates="operator")


class TrafficSource(Base):
    __tablename__ = "traffic_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tickets: Mapped[List["Ticket"]] = relationship(back_populates="traffic_source")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_name: Mapped[str] = mapped_column(String(300), nullable=False)
    client_phone: Mapped[Optional[str]] = mapped_column(String(50))
    client_contact: Mapped[Optional[str]] = mapped_column(String(300))

    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus), default=TicketStatus.NEW, nullable=False
    )

    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False)
    traffic_source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("traffic_sources.id")
    )

    description: Mapped[Optional[str]] = mapped_column(Text)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    operator: Mapped["Operator"] = relationship(back_populates="tickets")
    traffic_source: Mapped[Optional["TrafficSource"]] = relationship(
        back_populates="tickets"
    )
    payments: Mapped[List["Payment"]] = relationship(back_populates="ticket")
    action_logs: Mapped[List["ActionLog"]] = relationship(back_populates="ticket")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="payments")


class ClientList(Base):
    __tablename__ = "client_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_type: Mapped[ListType] = mapped_column(Enum(ListType), nullable=False)
    client_name: Mapped[Optional[str]] = mapped_column(String(300))
    client_phone: Mapped[Optional[str]] = mapped_column(String(50))
    client_contact: Mapped[Optional[str]] = mapped_column(String(300))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"))
    added_by_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operator_id: Mapped[Optional[int]] = mapped_column(ForeignKey("operators.id"))
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"))
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    operator: Mapped[Optional["Operator"]] = relationship(back_populates="action_logs")
    ticket: Mapped[Optional["Ticket"]] = relationship(back_populates="action_logs")
