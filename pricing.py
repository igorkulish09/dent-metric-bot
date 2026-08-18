"""
Логіка розрахунку вартості ремонту вм'ятини.

Все, що нижче, — орієнтовні базові ціни та коефіцієнти.
Постав СВОЇ реальні ціни — ключі (id) чіпати не треба, міняй тільки
значення "name" (якщо хочеш перейменувати) і числа.
"""

# Пошкоджений елемент -> (назва, базова ціна за середню складність)
ELEMENTS = {
    "front_bumper": ("Передній бампер", 3000),
    "front_fender": ("Переднє крило", 3000),
    "front_door": ("Передні двері", 3500),
    "rear_door": ("Задні двері", 3500),
    "rear_fender": ("Заднє крило", 3200),
    "rear_bumper": ("Задній бампер", 3500),
    "roof_pillar": ("Стійка даху", 4000),
    "roof": ("Дах", 5000),
    "hood": ("Капот", 4500),
    "trunk": ("Кришка багажника", 4000),
    "sill": ("Поріг", 3000),
}

TECHNOLOGY = {
    "no_paint": ("Без фарбування", 1.5),
    "with_paint": ("З фарбуванням", 1.0),
}

COMPLEXITY = {
    "medium": ("Середня (стандартна вм'ятина)", 1.0),
    "high": ("Висока (гостра / із заломом)", 1.5),
}

MATERIAL = {
    "steel": ("Сталь", 1.0),
    "aluminum": ("Алюміній", 2.5),
    "plastic": ("Пластмаса", 0.9),
}

CAR_CLASS = {
    "standard": ("Стандарт", 1.0),
    "premium": ("Преміум / Новий", 1.5),
}

ROUND_STEP = 100  # округлення підсумкової ціни до найближчих 100


def calc_price(element: str, technology: str, complexity: str,
                material: str, car_class: str) -> int:
    base = ELEMENTS[element][1]
    mult = (
        TECHNOLOGY[technology][1]
        * COMPLEXITY[complexity][1]
        * MATERIAL[material][1]
        * CAR_CLASS[car_class][1]
    )
    price = base * mult
    price = round(price / ROUND_STEP) * ROUND_STEP
    return int(price)


def describe_dent(element: str, technology: str, complexity: str,
                   material: str, car_class: str, price: int) -> str:
    return (
        f"Елемент: {ELEMENTS[element][0]}\n"
        f"Технологія: {TECHNOLOGY[technology][0]}\n"
        f"Складність: {COMPLEXITY[complexity][0]}\n"
        f"Матеріал: {MATERIAL[material][0]}\n"
        f"Клас авто: {CAR_CLASS[car_class][0]}\n"
        f"Ціна: {price} грн"
    )
