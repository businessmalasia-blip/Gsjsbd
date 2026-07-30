from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import TicketStatus, ListType, TrafficSource
from typing import List


def main_menu_kb(is_supervisor: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Новое обращение", callback_data="ticket:new")
    builder.button(text="🔍 Поиск обращений", callback_data="ticket:search")
    builder.button(text="📁 Мои обращения", callback_data="ticket:my")
    builder.button(text="📊 Отчёты", callback_data="report:menu")
    builder.button(text="🟢 Green List", callback_data="list:green")
    builder.button(text="⚪ White List", callback_data="list:white")
    builder.button(text="🔴 Black List", callback_data="list:black")
    if is_supervisor:
        builder.button(text="👥 Аналитика операторов", callback_data="report:operators")
        builder.button(text="📈 Аналитика трафика", callback_data="report:traffic")
        builder.button(text="📜 Журнал действий", callback_data="log:view")
        builder.button(text="⚙️ Управление", callback_data="admin:menu")
    builder.adjust(2, 2, 3, 2, 1)
    return builder.as_markup()


def ticket_status_kb(ticket_id: int, current_status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    statuses = {
        TicketStatus.NEW: "🆕 Новый",
        TicketStatus.IN_PROGRESS: "🔄 В работе",
        TicketStatus.PAID: "✅ Оплачен",
        TicketStatus.CANCELLED: "❌ Отменён",
        TicketStatus.ON_HOLD: "⏸ На паузе",
    }
    for status, label in statuses.items():
        if status.value != current_status:
            builder.button(
                text=label,
                callback_data=f"status:{ticket_id}:{status.value}"
            )
    builder.button(text="💰 Добавить оплату", callback_data=f"payment:{ticket_id}")
    builder.button(text="📋 Добавить в список", callback_data=f"addlist:{ticket_id}")
    builder.button(text="🔙 Назад", callback_data="menu:main")
    builder.adjust(2, 2, 1, 2, 1)
    return builder.as_markup()


def report_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Сегодня", callback_data="report:period:today")
    builder.button(text="📅 Вчера", callback_data="report:period:yesterday")
    builder.button(text="📅 Неделя", callback_data="report:period:week")
    builder.button(text="📅 Месяц", callback_data="report:period:month")
    builder.button(text="📅 Произвольный период", callback_data="report:period:custom")
    builder.button(text="🔙 Назад", callback_data="menu:main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def traffic_sources_kb(sources: List[TrafficSource]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for source in sources:
        builder.button(text=source.name, callback_data=f"source:{source.id}")
    builder.button(text="➕ Другой источник", callback_data="source:new")
    builder.button(text="⏭ Пропустить", callback_data="source:skip")
    builder.adjust(2)
    return builder.as_markup()


def list_type_kb(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Green List", callback_data=f"list_add:{ticket_id}:green")
    builder.button(text="⚪ White List", callback_data=f"list_add:{ticket_id}:white")
    builder.button(text="🔴 Black List", callback_data=f"list_add:{ticket_id}:black")
    builder.button(text="🔙 Отмена", callback_data=f"ticket:view:{ticket_id}")
    builder.adjust(3, 1)
    return builder.as_markup()


def confirm_kb(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"{prefix}:confirm")
    builder.button(text="❌ Отмена", callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="menu:main")
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="menu:main")
    return builder.as_markup()


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Список операторов", callback_data="admin:operators")
    builder.button(text="🔑 Изменить роль", callback_data="admin:change_role")
    builder.button(text="📡 Источники трафика", callback_data="admin:sources")
    builder.button(text="🔙 Назад", callback_data="menu:main")
    builder.adjust(2, 1, 1)
    return builder.as_markup()
