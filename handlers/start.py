"""
Стартовий обробник — привітання та вибір режиму розрахунку.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import RepairForm
from keyboards import mode_choice_kb

router = Router()

WELCOME_TEXT = (
    "👋 Вітаю! Я допоможу орієнтовно розрахувати вартість кузовного ремонту авто "
    "(тріщини, вм'ятини, сколи, подряпини тощо).\n\n"
    "Можу оцінити пошкодження одразу по фото 📸, або можемо порахувати вручну ✍️.\n\n"
    "⚠️ Це попередній розрахунок. Точну ціну назве майстер після живого огляду."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(RepairForm.choosing_mode)
    await message.answer(WELCOME_TEXT, reply_markup=mode_choice_kb())


@router.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(RepairForm.choosing_mode)
    await callback.message.answer(WELCOME_TEXT, reply_markup=mode_choice_kb())
    await callback.answer()
