from decimal import Decimal
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from app.bot.states.order import PriceState
from app.database.models import Price
from app.database.session import SessionLocal
from app.bot.auth import is_admin

router = Router()

@router.message(F.text == "💰 Ціни")
async def prices(message: Message):
    async with SessionLocal() as session:
        items = (await session.scalars(select(Price).order_by(Price.id))).all()
    rows = [[InlineKeyboardButton(text=f"#{p.id} {p.element} | {p.car_class} | {p.complexity} | {p.material} — {p.amount} грн", callback_data=f"price:{p.id}")] for p in items]
    await message.answer("💰 <b>Прайс</b>\nНатисніть тариф, щоб змінити ціну.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@router.callback_query(F.data.startswith("price:"))
async def price_select(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ Зміна прайсу доступна лише адміністратору.", show_alert=True); return
    pid=int(call.data.split(":")[1])
    async with SessionLocal() as session: p=await session.get(Price,pid)
    if not p: await call.answer("Тариф не знайдено",show_alert=True); return
    await state.set_state(PriceState.amount); await state.update_data(price_id=pid)
    await call.message.answer(f"Тариф #{p.id}\n{p.element} / {p.complexity} / {p.material} / {p.car_class}\nПоточна ціна: {p.amount} грн\n\nВведіть нову ціну:")
    await call.answer()

@router.message(PriceState.amount)
async def price_update(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): await state.clear(); await message.answer("⛔ Недостатньо прав."); return
    try:
        amount=Decimal(message.text.replace(",",".")); assert amount>=0
    except Exception: await message.answer("Введіть коректну суму, наприклад 2500."); return
    data=await state.get_data()
    async with SessionLocal() as session:
        p=await session.get(Price,data["price_id"])
        if not p: await message.answer("Тариф не знайдено."); await state.clear(); return
        p.amount=amount; await session.commit()
    await state.clear(); await message.answer(f"✅ Ціну оновлено: {amount} грн.")
