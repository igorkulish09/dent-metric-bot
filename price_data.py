"""
Прайс-лист та коефіцієнти для розрахунку вартості кузовного ремонту.
Усі суми умовні (в грн) — відредагуйте під реальні ціни вашого СТО.
"""

# Класи авто впливають на вартість деталей/фарби (коефіцієнт)
CAR_CLASSES = {
    "economy": {
        "label": "Економ",
        "brands": ["ZAZ", "Daewoo", "Lada", "Chery", "Geely", "Ravon"],
        "coef": 0.85,
    },
    "standard": {
        "label": "Стандарт",
        "brands": ["Volkswagen", "Skoda", "Toyota", "Renault", "Hyundai",
                   "Kia", "Ford", "Opel", "Nissan", "Mazda", "Honda"],
        "coef": 1.0,
    },
    "premium": {
        "label": "Преміум",
        "brands": ["BMW", "Mercedes-Benz", "Audi", "Lexus", "Volvo",
                    "Porsche", "Land Rover", "Jaguar"],
        "coef": 1.4,
    },
}

# Популярні марки для швидкого вибору кнопками (можна ввести і вручну)
POPULAR_BRANDS = [
    "Volkswagen", "Toyota", "BMW", "Mercedes-Benz", "Renault",
    "Hyundai", "Kia", "Ford", "Skoda", "Nissan", "Lada", "Інша",
]

# Типи пошкоджень: базова ціна робіт (за одну одиницю пошкодження середнього розміру)
DAMAGE_TYPES = {
    "crack": {"label": "🔹 Тріщина (бампер/пластик)", "base_price": 800},
    "dent": {"label": "🔸 Вм'ятина", "base_price": 1200},
    "chip": {"label": "◽ Скол фарби/каменем", "base_price": 400},
    "scratch": {"label": "➖ Подряпина", "base_price": 500},
    "paint": {"label": "🎨 Потрібне повне фарбування панелі", "base_price": 2500},
    "rust": {"label": "🟤 Корозія/іржа", "base_price": 1800},
}

# Коефіцієнт залежно від розміру пошкодження
DAMAGE_SIZE = {
    "small":  {"label": "Мале (до 5 см)",   "coef": 0.6},
    "medium": {"label": "Середнє (5-20 см)", "coef": 1.0},
    "large":  {"label": "Велике (понад 20 см)", "coef": 1.8},
}

# Додаткові роботи (можна вибрати декілька, чекбокс-стиль)
EXTRA_WORKS = {
    "polish":      {"label": "Полірування панелі",           "price": 600},
    "primer":      {"label": "Ґрунтування",                   "price": 350},
    "part_remove": {"label": "Зняття/встановлення деталі",    "price": 500},
    "matching":    {"label": "Підбір кольору по коду авто",   "price": 300},
    "protection":  {"label": "Захисне покриття після фарбування", "price": 450},
}

# Коефіцієнт "надбавки за вік" — старі авто часто потребують більше підготовчих робіт
def year_coefficient(year: int) -> float:
    from datetime import date
    age = date.today().year - year
    if age <= 3:
        return 1.0
    if age <= 7:
        return 1.05
    if age <= 15:
        return 1.12
    return 1.2


def get_car_class_coef(brand: str) -> float:
    for cls in CAR_CLASSES.values():
        if brand in cls["brands"]:
            return cls["coef"]
    return 1.0  # якщо марка невідома — стандартний коефіцієнт


def calculate_price(brand: str, year: int, damage_type: str,
                     damage_size: str, extra_works: list[str]) -> dict:
    """
    Повертає деталізований розрахунок вартості ремонту.
    """
    base = DAMAGE_TYPES[damage_type]["base_price"]
    size_coef = DAMAGE_SIZE[damage_size]["coef"]
    class_coef = get_car_class_coef(brand)
    age_coef = year_coefficient(year)

    main_work_price = round(base * size_coef * class_coef * age_coef)

    extras_total = sum(EXTRA_WORKS[w]["price"] for w in extra_works)
    extras_detail = [
        {"label": EXTRA_WORKS[w]["label"], "price": EXTRA_WORKS[w]["price"]}
        for w in extra_works
    ]

    total = main_work_price + extras_total

    return {
        "main_work_price": main_work_price,
        "extras_detail": extras_detail,
        "extras_total": extras_total,
        "total": total,
        "class_coef": class_coef,
        "age_coef": age_coef,
        "size_coef": size_coef,
    }
