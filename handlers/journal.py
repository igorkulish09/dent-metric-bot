from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import keyboards as kb
import database as db

router = Router()


@router.message(F.text == "📒 Журнал")
async def show_journal(message: Message):
    orders = await db.list_orders(message.from_user.id, "in_progress")
    if not orders:
        await message.answer("Журнал порожній. Активних замовлень немає.", reply_markup=kb.main_menu())
        return
    await message.answer(
        "📒 Активні замовлення (в роботі):",
        reply_markup=kb.orders_list_kb(orders),
    )


@router.message(F.text == "🕑 Історія")
async def show_history(message: Message):
    orders = await db.list_orders(message.from_user.id, "completed")
    if not orders:
        await message.answer("Історія порожня. Завершених замовлень ще немає.", reply_markup=kb.main_menu())
        return
    await message.answer(
        "🕑 Завершені замовлення:",
        reply_markup=kb.orders_list_kb(orders),
    )


@router.callback_query(F.data == "back_to_list")
async def back_to_list(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data.startswith("order_open:"))
async def open_order(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    from handlers.calculator import show_order_card
    await show_order_card(callback.message, order_id)
    await callback.answer()
