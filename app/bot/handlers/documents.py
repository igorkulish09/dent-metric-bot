from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy import select, func
from app.database.models import Order, Car, Dent, Payment
from app.database.session import SessionLocal
from app.services.pdf import create_act

router = Router()

@router.callback_query(F.data.startswith("act:"))
async def act(call: CallbackQuery):
    oid = int(call.data.split(":")[1])
    async with SessionLocal() as session:
        order = await session.get(Order, oid)
        car = await session.get(Car, order.car_id)
        dents = (await session.scalars(select(Dent).where(Dent.order_id == oid).order_by(Dent.number))).all()
        paid = await session.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.order_id == oid))
    path = create_act(order, car, dents, paid)
    await call.message.answer_document(FSInputFile(path), caption=f"📄 Акт до замовлення #{oid}")
    await call.answer()
