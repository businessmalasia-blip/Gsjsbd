from aiogram.fsm.state import State, StatesGroup


class RegistrationForm(StatesGroup):
    full_name = State()


class TicketForm(StatesGroup):
    client_phone = State()
    client_contact = State()
    traffic_source = State()
    model_id = State()
    master_id = State()
    session_start = State()
    session_duration = State()
    description = State()
    confirm = State()


class StatusChangeForm(StatesGroup):
    ticket_id = State()
    new_status = State()
    cancellation_reason = State()
    departure_reason = State()


class PaymentForm(StatesGroup):
    ticket_id = State()
    payment_type = State()
    extra_time_minutes = State()
    amount = State()
    comment = State()


class SearchForm(StatesGroup):
    query = State()


class ListForm(StatesGroup):
    list_type = State()
    ticket_id_or_manual = State()
    client_name = State()
    client_phone = State()
    reason = State()


class ReportForm(StatesGroup):
    period = State()
    date_from = State()
    date_to = State()


class TrafficSourceForm(StatesGroup):
    name = State()


class ModelForm(StatesGroup):
    name = State()


class MasterForm(StatesGroup):
    name = State()


class AdminForm(StatesGroup):
    operator_telegram_id = State()
    new_role = State()
