from decimal import Decimal
from sqlalchemy import select
from app.database.models import Price
from app.database.session import SessionLocal


async def get_price(element, technology, complexity, material, car_class):
    async with SessionLocal() as session:
        stmt = select(Price).where(
            Price.element == element,
            Price.technology == technology,
            Price.complexity == complexity,
            Price.material == material,
            Price.car_class == car_class,
            Price.active.is_(True),
        )
        obj = await session.scalar(stmt)
        return obj.amount if obj else Decimal("0")


async def list_prices():
    async with SessionLocal() as session:
        return (await session.scalars(select(Price).order_by(
            Price.element, Price.car_class, Price.complexity, Price.material
        ))).all()


async def update_price(price_id: int, amount: Decimal):
    async with SessionLocal() as session:
        obj = await session.get(Price, price_id)
        if not obj:
            return False
        obj.amount = amount
        await session.commit()
        return True
