from decimal import Decimal
from sqlalchemy import select
from app.database.models import Base, BusinessSettings, Price
from app.database.session import engine, SessionLocal

ELEMENTS = [
    "Передній бампер", "Задній бампер", "Переднє крило", "Заднє крило",
    "Передні двері", "Задні двері", "Капот", "Кришка багажника",
    "Стійка даху", "Поріг", "Дах", "Інше",
]
TECHNOLOGIES = ["Без фарбування (PDR)"]
COMPLEXITIES = ["Середня", "Висока"]
MATERIALS = ["Сталь", "Алюміній", "Пластик"]
CAR_CLASSES = ["Стандарт", "Преміум"]


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        settings = await session.get(BusinessSettings, 1)
        if not settings:
            session.add(BusinessSettings(id=1))
        count = await session.scalar(select(Price.id).limit(1))
        if count is None:
            base = {
                ("Стандарт", "Середня", "Сталь"): 1500,
                ("Стандарт", "Висока", "Сталь"): 2500,
                ("Стандарт", "Середня", "Алюміній"): 1800,
                ("Стандарт", "Висока", "Алюміній"): 3000,
                ("Стандарт", "Середня", "Пластик"): 1600,
                ("Стандарт", "Висока", "Пластик"): 2600,
                ("Преміум", "Середня", "Сталь"): 2200,
                ("Преміум", "Висока", "Сталь"): 3500,
                ("Преміум", "Середня", "Алюміній"): 2500,
                ("Преміум", "Висока", "Алюміній"): 4000,
                ("Преміум", "Середня", "Пластик"): 2200,
                ("Преміум", "Висока", "Пластик"): 3600,
            }
            for car_class in CAR_CLASSES:
                for complexity in COMPLEXITIES:
                    for material in MATERIALS:
                        for element in ELEMENTS:
                            session.add(Price(
                                element=element,
                                technology=TECHNOLOGIES[0],
                                complexity=complexity,
                                material=material,
                                car_class=car_class,
                                amount=Decimal(base[(car_class, complexity, material)])
                            ))
        await session.commit()
