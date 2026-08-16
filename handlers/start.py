from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

import keyboards as kb

router = Router()

WELCOME = (
    "👋 Привіт! Це бот для розрахунку вартості видалення вм'ятин та ведення замовлень.\n\n"
    "🧮 Новий розрахунок — порахувати вартість ремонту і створити замовлення\n"
    "📒 Журнал — активні замовлення (в роботі)\n"
    "🕑 Історія — завершені замовлення\n"
    "⚙️ Ще — довідка та контакти"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=kb.main_menu(message.from_user.id in __import__("config").ADMIN_USER_IDS))


@router.message(Command("cancel"))
@router.message(F.text == "❌ Скасувати")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Скасовано.", reply_markup=kb.main_menu(message.from_user.id in __import__("config").ADMIN_USER_IDS))


@router.message(F.text == "⚙️ Ще")
async def show_more(message: Message):
    import config
    text = (
        "⚙️ <b>Довідка</b>\n\n"
        "Цей бот — внутрішній інструмент для розрахунку вартості PDR-ремонту "
        "та ведення замовлень.\n\n"
        f"<b>Виконавець:</b> {config.COMPANY_NAME}\n"
        f"{config.COMPANY_ADDRESS}\n"
        f"{config.COMPANY_PHONE}\n\n"
        "Базові ціни та коефіцієнти можна змінити у файлі pricing.py на сервері."
    )
    await message.answer(text, reply_markup=kb.main_menu())
