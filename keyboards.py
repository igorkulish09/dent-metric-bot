from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
import calendar as pycal
from datetime import date
import pricing

MONTHS_UA = [
    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень",
]
WEEKDAYS_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🧮 Новий розрахунок"), KeyboardButton(text="📒 Журнал")],
        [KeyboardButton(text="📅 Розклад"), KeyboardButton(text="🕑 Історія")],
        [KeyboardButton(text="⚙️ Ще")],
    ]
    if is_admin:
        kb.append([KeyboardButton(text="👑 Адміністрування")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )


def skip_cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➡️ Пропустити")], [KeyboardButton(text="❌ Скасувати")]],
        resize_keyboard=True,
    )


def _options_kb(options: dict, prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for key, val in options.items():
        name = val[0]
        rows.append([InlineKeyboardButton(text=name, callback_data=f"{prefix}:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def element_kb() -> InlineKeyboardMarkup:
    return _options_kb(pricing.ELEMENTS, "elem")


def technology_kb() -> InlineKeyboardMarkup:
    return _options_kb(pricing.TECHNOLOGY, "tech")


def complexity_kb() -> InlineKeyboardMarkup:
    return _options_kb(pricing.COMPLEXITY, "cplx")


def material_kb() -> InlineKeyboardMarkup:
    return _options_kb(pricing.MATERIAL, "mtrl")


def car_class_kb() -> InlineKeyboardMarkup:
    return _options_kb(pricing.CAR_CLASS, "clss")


def dent_added_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ Додати ще вм'ятину", callback_data="dent_more")],
        [InlineKeyboardButton(text="✅ Завершити розрахунок", callback_data="dent_finish")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_card_kb(order_id: int, status: str, has_appointment: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ Додати вм'ятину", callback_data=f"order_adddent:{order_id}")],
        [InlineKeyboardButton(text="📄 Сформувати акт (PDF)", callback_data=f"order_act:{order_id}")],
        [InlineKeyboardButton(text="🗑 Видалити вм'ятину", callback_data=f"order_dents:{order_id}")],
    ]
    if has_appointment:
        rows.append([InlineKeyboardButton(text="📅 Змінити дату запису", callback_data=f"order_schedule:{order_id}")])
        rows.append([InlineKeyboardButton(text="🚫 Скасувати запис", callback_data=f"order_unschedule:{order_id}")])
    else:
        rows.append([InlineKeyboardButton(text="📅 Записати на ремонт", callback_data=f"order_schedule:{order_id}")])
    if status != "completed":
        rows.append([InlineKeyboardButton(text="✅ Завершити замовлення", callback_data=f"order_complete:{order_id}")])
    rows.append([InlineKeyboardButton(text="🗑 Видалити замовлення", callback_data=f"order_delete:{order_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dents_delete_kb(order_id: int, dents: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for i, d in enumerate(dents, start=1):
        name = pricing.ELEMENTS[d["element"]][0]
        rows.append([InlineKeyboardButton(
            text=f"🗑 {i}. {name} — {d['price']} грн",
            callback_data=f"dent_delete:{d['id']}:{order_id}",
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"order_open:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_list_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for o in orders:
        title = o["car_make"] or o["client_name"] or f"Замовлення #{o['id']}"
        rows.append([InlineKeyboardButton(
            text=f"#{o['id']} — {title}",
            callback_data=f"order_open:{o['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else InlineKeyboardMarkup(inline_keyboard=[])


# ---------- календар ----------

def calendar_kb(
    year: int,
    month: int,
    prefix: str,
    occupied_dates: set[str] | None = None,
) -> InlineKeyboardMarkup:
    """Місячний календар із візуальним статусом днів.

    🟢 — вільний робочий день
    🔴 — день уже зайнятий записом
    ⚪ — неділя / вихідний

    occupied_dates передається у форматі YYYY-MM-DD.
    """
    occupied_dates = occupied_dates or set()

    rows = [[
        InlineKeyboardButton(
            text=f"📅 {MONTHS_UA[month - 1]} {year}",
            callback_data="noop",
        )
    ]]
    rows.append([
        InlineKeyboardButton(text=d, callback_data="noop")
        for d in WEEKDAYS_UA
    ])

    today = date.today()
    cal = pycal.Calendar(firstweekday=0)

    for week in cal.monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
                continue

            current = date(year, month, day)
            date_str = current.isoformat()

            if current.weekday() == 6:
                # Неділя — завжди вихідний і не натискається.
                label = f"⚪{day}"
                callback_data = "noop"
            elif date_str in occupied_dates:
                # Зайнятий день. У режимі вибору запису його не можна
                # обрати, щоб не створити накладку.
                label = f"🔴{day}"
                callback_data = f"{prefix}busy:{year}:{month:02d}:{day:02d}"
            else:
                label = f"🟢{day}"
                if current == today:
                    label = f"🟢•{day}"
                callback_data = f"{prefix}:{year}:{month:02d}:{day:02d}"

            row.append(
                InlineKeyboardButton(text=label, callback_data=callback_data)
            )
        rows.append(row)

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    rows.append([
        InlineKeyboardButton(
            text="◀️",
            callback_data=f"{prefix}nav:{prev_year}:{prev_month:02d}",
        ),
        InlineKeyboardButton(
            text="❌ Закрити",
            callback_data=f"{prefix}cancel",
        ),
        InlineKeyboardButton(
            text="▶️",
            callback_data=f"{prefix}nav:{next_year}:{next_month:02d}",
        ),
    ])

    rows.append([
        InlineKeyboardButton(text="🟢 Вільно", callback_data="noop"),
        InlineKeyboardButton(text="🔴 Зайнято", callback_data="noop"),
        InlineKeyboardButton(text="⚪ Неділя", callback_data="noop"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_slots_kb() -> InlineKeyboardMarkup:
    hours = [f"{h:02d}:00" for h in range(9, 19)]
    rows = []
    row = []
    for i, h in enumerate(hours, start=1):
        row.append(InlineKeyboardButton(text=h, callback_data=f"schtime:{h}"))
        if i % 5 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✏️ Ввести інший час", callback_data="schtime_manual")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад до календаря", callback_data="schtime_back")])
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="schcalcancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
