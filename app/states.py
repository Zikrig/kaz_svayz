from aiogram.fsm.state import State, StatesGroup


class RegistrationState(StatesGroup):
    waiting_phone = State()
    confirm_phone = State()


class ConsumerRequestState(StatesGroup):
    waiting_text = State()
    waiting_photos = State()
    preview = State()


class SupplierResponseState(StatesGroup):
    waiting_price = State()
    waiting_eta = State()
    waiting_description = State()
    waiting_photos = State()
    preview = State()


class AdminState(StatesGroup):
    waiting_set_role_tg = State()
    waiting_set_role_name = State()
    waiting_broadcast = State()
