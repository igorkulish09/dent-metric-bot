from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    client_name = State()
    client_phone = State()
    car_make = State()
    car_model = State()
    car_plate = State()


class DentForm(StatesGroup):
    element = State()
    technology = State()
    complexity = State()
    material = State()
    car_class = State()
    width = State()
    length = State()


class ScheduleForm(StatesGroup):
    manual_time = State()
