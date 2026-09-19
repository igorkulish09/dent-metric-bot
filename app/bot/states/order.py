from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    customer = State()
    brand = State()
    model = State()
    plate = State()
    car_class = State()
    dent_photo = State()
    dent_size = State()
    dent_element = State()
    dent_technology = State()
    dent_complexity = State()
    dent_material = State()
    factor = State()
    factor_price = State()
    finish = State()

class PaymentState(StatesGroup):
    amount = State()

class BookingState(StatesGroup):
    date = State()
    days = State()

class PriceState(StatesGroup):
    price_id = State()
    amount = State()

class SettingsState(StatesGroup):
    business_name = State()
    performer_name = State()
    tax_id = State()
    phone = State()
