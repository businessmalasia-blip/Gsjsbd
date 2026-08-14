import io
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from aiogram import Bot
from aiogram.types import BufferedInputFile
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from config import settings
from database.connection import async_session_factory
from database.crud import get_export_tickets
from database.models import Ticket

HEADERS = [
    "№", "Дата", "Время", "Телефон", "Контакт", "Модель",
    "Источник", "Статус клиента", "Мастер", "Длительность (мин)",
    "Результат", "Комментарий",
    "Оплата за отмену", "Оплата сеанса", "Консумация",
    "Доп. время (мин)", "Оплата за доп. время", "Оператор",
]

CLIENT_STATUS_MAP = {
    "new": "Новый",
    "white_list": "Белый список",
    "black_list": "Чёрный список",
}

RESULT_MAP = {
    "positive_lead": "Позитивный лид",
    "booking": "Бронь",
    "general_lead": "Общий лид",
}


def _ticket_row(ticket: Ticket) -> list:
    # aggregate payments by type
    pay: dict = {"session": Decimal(0), "cancellation": Decimal(0),
                 "service": Decimal(0), "extra_time": Decimal(0)}
    extra_mins = 0
    for p in ticket.payments:
        ptype = p.payment_type.value
        pay[ptype] = pay.get(ptype, Decimal(0)) + p.amount
        if ptype == "extra_time" and p.extra_time_minutes:
            extra_mins += p.extra_time_minutes

    tz = pytz.timezone(settings.TIMEZONE)
    created = ticket.created_at
    if created.tzinfo is None:
        created = pytz.utc.localize(created)
    created = created.astimezone(tz)

    comment = ticket.cancellation_reason or ticket.departure_reason or ""
    client_status = CLIENT_STATUS_MAP.get(
        ticket.client_status.value if ticket.client_status else "new", "Новый"
    )
    result = RESULT_MAP.get(
        ticket.result_category.value if ticket.result_category else "", ""
    )

    return [
        ticket.id,
        created.strftime("%d.%m.%Y"),
        created.strftime("%H:%M"),
        ticket.client_phone or "",
        ticket.client_contact or "",
        ticket.model.name if ticket.model else "",
        ticket.traffic_source.name if ticket.traffic_source else "",
        client_status,
        ticket.master.name if ticket.master else "",
        ticket.session_duration or "",
        result,
        comment,
        float(pay["cancellation"]) or "",
        float(pay["session"]) or "",
        float(pay["service"]) or "",
        extra_mins or "",
        float(pay["extra_time"]) or "",
        ticket.operator.full_name if ticket.operator else "",
    ]


def generate_excel(tickets: list, date_from: datetime, date_to: datetime) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Выгрузка"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2E4057")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, header in enumerate(HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center

    ws.row_dimensions[1].height = 36

    alt_fill = PatternFill("solid", fgColor="EEF2F7")
    for row_idx, ticket in enumerate(tickets, 2):
        row_data = _ticket_row(ticket)
        fill = alt_fill if row_idx % 2 == 0 else None
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if fill:
                cell.fill = fill

    col_widths = [6, 11, 7, 16, 20, 14, 12, 14, 14, 12,
                  16, 28, 14, 14, 12, 14, 16, 18]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}1"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def run_daily_export(bot: Bot) -> None:
    if not settings.EXPORT_CHAT_ID:
        return

    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    date_to = now.replace(hour=10, minute=0, second=0, microsecond=0)
    date_from = date_to - timedelta(days=1)

    async with async_session_factory() as session:
        tickets = await get_export_tickets(session, date_from, date_to)

    if not tickets:
        await bot.send_message(
            settings.EXPORT_CHAT_ID,
            f"📊 Выгрузка за {date_from.strftime('%d.%m.%Y')}: нет обращений."
        )
        return

    excel_bytes = generate_excel(tickets, date_from, date_to)
    filename = f"crm_export_{date_from.strftime('%d%m%Y')}.xlsx"
    caption = (
        f"📊 Выгрузка за {date_from.strftime('%d.%m.%Y')} 10:00 — "
        f"{date_to.strftime('%d.%m.%Y')} 10:00\n"
        f"Обращений: {len(tickets)}"
    )
    await bot.send_document(
        settings.EXPORT_CHAT_ID,
        BufferedInputFile(excel_bytes, filename=filename),
        caption=caption,
    )
