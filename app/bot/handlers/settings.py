from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.bot.states.order import SettingsState
from app.database.models import BusinessSettings
from app.database.session import SessionLocal

router = Router()
FIELDS = {
    "name": ("business_name", SettingsState.business_name, "нову назву"),
    "performer": ("performer_name", SettingsState.performer_name, "ПІБ/назву виконавця"),
    "tax": ("performer_tax_id", SettingsState.tax_id, "ІПН"),
    "phone": ("phone", SettingsState.phone, "номер телефону"),
}

@router.message(F.text == "⚙️ Налаштування")
async def settings_menu(message: Message):
    async with SessionLocal() as session:
        s = await session.get(BusinessSettings, 1)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Назва", callback_data="settings:name"),
         InlineKeyboardButton(text="👤 Виконавець", callback_data="settings:performer")],
        [InlineKeyboardButton(text="🧾 ІПН", callback_data="settings:tax"),
         InlineKeyboardButton(text="📞 Телефон", callback_data="settings:phone")],
    ])
    await message.answer(
        f"⚙️ <b>Налаштування</b>\n\n"
        f"Назва: {s.business_name}\n"
        f"Виконавець: {s.performer_name or '-'}\n"
        f"ІПН: {s.performer_tax_id or '-'}\n"
        f"Телефон: {s.phone or '-'}",
        reply_markup=kb, parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("settings:"))
async def settings_select(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    field, state_cls, prompt = FIELDS[key]
    await state.set_state(state_cls)
    await state.update_data(field=field)
    await call.message.answer(f"Введіть {prompt}:")
    await call.answer()

async def save_field(message: Message, state: FSMContext):
    data = await state.get_data()
    async with SessionLocal() as session:
        s = await session.get(BusinessSettings, 1)
        setattr(s, data["field"], message.text.strip())
        await session.commit()
    await state.clear()
    await message.answer("✅ Налаштування збережено.")

@router.message(SettingsState.business_name)
async def save_name(message: Message, state: FSMContext):
    await save_field(message, state)

@router.message(SettingsState.performer_name)
async def save_performer(message: Message, state: FSMContext):
    await save_field(message, state)

@router.message(SettingsState.tax_id)
async def save_tax(message: Message, state: FSMContext):
    await save_field(message, state)

@router.message(SettingsState.phone)
async def save_phone(message: Message, state: FSMContext):
    await save_field(message, state)
