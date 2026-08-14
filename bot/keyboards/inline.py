from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import TicketStatus, ListType, TrafficSource, Model, Master
from typing import List
from bot.i18n import t


def main_menu_kb(lang: str = "ru", is_supervisor: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("new_ticket", lang), callback_data="ticket:new")
    builder.button(text=t("search", lang), callback_data="ticket:search")
    builder.button(text=t("my_tickets", lang), callback_data="ticket:my")
    builder.button(text=t("reports", lang), callback_data="report:menu")
    builder.button(text=t("green_list", lang), callback_data="list:green")
    builder.button(text=t("white_list", lang), callback_data="list:white")
    builder.button(text=t("black_list", lang), callback_data="list:black")
    if is_supervisor:
        builder.button(text=t("operator_analytics", lang), callback_data="report:operators")
        builder.button(text=t("traffic_analytics", lang), callback_data="report:traffic")
        builder.button(text=t("action_log", lang), callback_data="log:view")
        builder.button(text=t("management", lang), callback_data="admin:menu")
    builder.button(text=t("change_language", lang), callback_data="lang:toggle")
    builder.adjust(2, 2, 3, 2, 1, 1)
    return builder.as_markup()


def ticket_status_kb(ticket_id: int, current_status: str, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    statuses = {
        TicketStatus.NEW: t("status_new", lang),
        TicketStatus.IN_PROGRESS: t("status_in_progress", lang),
        TicketStatus.PAID: t("status_paid", lang),
        TicketStatus.CANCELLED: t("status_cancelled", lang),
        TicketStatus.DEPARTED: t("status_departed", lang),
        TicketStatus.ON_HOLD: t("status_on_hold", lang),
    }
    for status, label in statuses.items():
        if status.value != current_status:
            builder.button(text=label, callback_data=f"status:{ticket_id}:{status.value}")
    builder.button(text=t("add_payment", lang), callback_data=f"payment:{ticket_id}")
    builder.button(text=t("set_result", lang), callback_data=f"result:{ticket_id}")
    builder.button(text=t("add_to_list_btn", lang), callback_data=f"addlist:{ticket_id}")
    builder.button(text=t("home", lang), callback_data="menu:main")
    builder.adjust(2, 2, 1, 3, 1)
    return builder.as_markup()


def report_period_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("today", lang), callback_data="report:period:today")
    builder.button(text=t("yesterday", lang), callback_data="report:period:yesterday")
    builder.button(text=t("week", lang), callback_data="report:period:week")
    builder.button(text=t("month", lang), callback_data="report:period:month")
    builder.button(text=t("custom_period", lang), callback_data="report:period:custom")
    builder.button(text=t("back", lang), callback_data="menu:main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def traffic_sources_kb(sources: List[TrafficSource], lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for source in sources:
        builder.button(text=source.name, callback_data=f"source:{source.id}")
    builder.button(text=t("add_source", lang), callback_data="source:new")
    builder.button(text=t("skip_source", lang), callback_data="source:skip")
    builder.adjust(2)
    return builder.as_markup()


def models_kb(models: List[Model], lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in models:
        builder.button(text=m.name, callback_data=f"model:{m.id}")
    builder.button(text=t("add_model", lang), callback_data="model:new")
    builder.button(text=t("skip_model", lang), callback_data="model:skip")
    builder.adjust(2)
    return builder.as_markup()


def masters_kb(masters: List[Master], lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in masters:
        builder.button(text=m.name, callback_data=f"master:{m.id}")
    builder.button(text=t("add_master", lang), callback_data="master:new")
    builder.button(text=t("skip_master", lang), callback_data="master:skip")
    builder.adjust(2)
    return builder.as_markup()


def payment_type_kb(ticket_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("pay_session", lang), callback_data=f"paytype:{ticket_id}:session")
    builder.button(text=t("pay_cancellation", lang), callback_data=f"paytype:{ticket_id}:cancellation")
    builder.button(text=t("pay_service", lang), callback_data=f"paytype:{ticket_id}:service")
    builder.button(text=t("pay_extra_time", lang), callback_data=f"paytype:{ticket_id}:extra_time")
    builder.button(text=t("cancel", lang), callback_data=f"ticket:view:{ticket_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def result_category_kb(ticket_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("result_positive_lead", lang), callback_data=f"setresult:{ticket_id}:positive_lead")
    builder.button(text=t("result_booking", lang), callback_data=f"setresult:{ticket_id}:booking")
    builder.button(text=t("result_general_lead", lang), callback_data=f"setresult:{ticket_id}:general_lead")
    builder.button(text=t("cancel", lang), callback_data=f"ticket:view:{ticket_id}")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


def list_type_kb(ticket_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("green_list", lang), callback_data=f"list_add:{ticket_id}:green")
    builder.button(text=t("white_list", lang), callback_data=f"list_add:{ticket_id}:white")
    builder.button(text=t("black_list", lang), callback_data=f"list_add:{ticket_id}:black")
    builder.button(text=t("cancel", lang), callback_data=f"ticket:view:{ticket_id}")
    builder.adjust(3, 1)
    return builder.as_markup()


def confirm_kb(prefix: str, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("confirm_btn", lang), callback_data=f"{prefix}:confirm")
    builder.button(text=t("cancel", lang), callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()


def cancel_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("cancel", lang), callback_data="menu:main")
    return builder.as_markup()


def back_to_menu_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("home", lang), callback_data="menu:main")
    return builder.as_markup()


def admin_menu_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("operators_list_btn", lang), callback_data="admin:operators")
    builder.button(text=t("change_role_btn", lang), callback_data="admin:change_role")
    builder.button(text=t("models_btn", lang), callback_data="admin:models")
    builder.button(text=t("masters_btn", lang), callback_data="admin:masters")
    builder.button(text=t("traffic_sources_btn", lang), callback_data="admin:sources")
    builder.button(text=t("back", lang), callback_data="menu:main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()
