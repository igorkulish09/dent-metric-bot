"""
Стани діалогу (FSM) — визначають, на якому кроці анкети знаходиться користувач.
"""
from aiogram.fsm.state import State, StatesGroup


class RepairForm(StatesGroup):
    choosing_mode = State()        # фото-аналіз чи ручний ввід
    waiting_photo = State()        # очікуємо фото пошкодження
    confirming_ai_result = State() # підтвердження результату AI-аналізу

    choosing_brand = State()
    entering_brand_manual = State()
    entering_model = State()
    entering_year = State()

    choosing_damage_type = State()
    choosing_damage_size = State()
    choosing_extra_works = State()

    entering_phone = State()       # контакт для запису на СТО
