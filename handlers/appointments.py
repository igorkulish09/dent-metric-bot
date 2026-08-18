from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
from states import ScheduleForm

router = Router()


# ---------- допоміжні ----------

def _fmt_date(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return d.strftime("%d.%m.%Y")


def _order_title(o: dict) -> str:
    return o["car_make"] or o["client_name"] or f"Замовлення #{o['id']}"


async def _occupied_dates(master_id: int) -> set[str]:
    """Повертає всі дати, на які вже є запис у майстра."""
    orders = await db.list_scheduled_orders(master_id)
    return {
        o["appointment_date"]
        for o in orders
        if o.get("appointment_date")
    }


async def _render_calendar(message, year: int, month: int, prefix: str, master_id: int):
    occupied = await _occupied_dates(master_id)
    await message.edit_reply_markup(
        reply_markup=kb.calendar_kb(
            year, month, prefix, occupied_dates=occupied
        )
    )


async def _send_calendar(message: Message, year: int, month: int, prefix: str, master_id: int):
    occupied = await _occupied_dates(master_id)
    await message.answer(
        "📅 <b>Календар запису</b>\n\n"
        "🟢 Вільно\n"
        "🔴 Зайнято\n"
        "⚪ Неділя — вихідний\n\n"
        "Оберіть вільний день:",
        reply_markup=kb.calendar_kb(
            year, month, prefix, occupied_dates=occupied
        ),
        parse_mode="HTML",
    )


# ================== ЗАПИС НА РЕМОНТ (з картки замовлення) ==================

@router.callback_query(F.data.startswith("order_schedule:"))
async def order_schedule_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(sch_order_id=order_id)

    today = date.today()
    await _send_calendar(
        callback.message,
        today.year,
        today.month,
        "schcal",
        callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("order_unschedule:"))
async def order_unschedule(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])
    await db.clear_appointment(order_id)
    await callback.answer("Запис скасовано")
    from handlers.calculator import show_order_card
    await callback.message.delete()
    await show_order_card(callback.message, order_id)


@router.callback_query(F.data.startswith("schcalnav:"))
async def schcal_nav(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    await _render_calendar(
        callback.message,
        int(year),
        int(month),
        "schcal",
        callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(F.data == "schcalcancel")
async def schcal_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await callback.message.delete()
    await callback.answer("Скасовано")


@router.callback_query(F.data.startswith("schcalbusy:"))
async def schcal_busy(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    date_str = f"{year}-{month}-{day}"
    orders = await db.list_orders_by_date(callback.from_user.id, date_str)

    if orders:
        lines = [
            f"🔴 <b>{_fmt_date(date_str)}</b> — день зайнятий",
            "",
        ]
        for order in orders:
            time = order.get("appointment_time") or "час не вказано"
            lines.append(f"🕐 {time} — {_order_title(order)}")
        await callback.answer("\n".join(lines), show_alert=True)
    else:
        # Race-condition fallback: календар був відкритий до того, як день
        # зайняли. Він уже вільний — перерендеримо календар.
        await callback.answer("День уже вільний. Оновіть календар.", show_alert=True)


@router.callback_query(F.data.startswith("schcal:"))
async def schcal_date_chosen(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    date_str = f"{year}-{month}-{day}"

    # Додаткова перевірка перед збереженням вибору.
    # Це захищає від ситуації, коли інший запис з'явився після відкриття календаря.
    orders = await db.list_orders_by_date(callback.from_user.id, date_str)
    if orders:
        await callback.answer(
            "🔴 Цей день уже зайнятий. Оберіть інший.",
            show_alert=True,
        )
        return

    selected = datetime.strptime(date_str, "%Y-%m-%d").date()
    if selected.weekday() == 6:
        await callback.answer("⚪ Неділя — вихідний день.", show_alert=True)
        return

    await state.update_data(sch_date=date_str)
    await callback.message.edit_text(
        f"📅 Дата: {_fmt_date(date_str)}\n\nОберіть час:",
        reply_markup=kb.time_slots_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "schtime_back")
async def schtime_back(callback: CallbackQuery, state: FSMContext):
    today = date.today()
    await _send_calendar(
        callback.message,
        today.year,
        today.month,
        "schcal",
        callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(F.data == "schtime_manual")
async def schtime_manual_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleForm.manual_time)
    await callback.message.edit_text(
        callback.message.text + "\n\n✏️ Напишіть час у форматі ГГ:ХХ, напр. 13:30",
        reply_markup=None,
    )
    await callback.answer()


@router.message(ScheduleForm.manual_time)
async def schtime_manual_entered(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("Невірний формат. Напишіть час як ГГ:ХХ, напр. 09:30")
        return
    await _save_appointment(message, state, text)


@router.callback_query(F.data.startswith("schtime:"))
async def schtime_chosen(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.split(":", 1)[1]
    await _save_appointment(callback, state, time_str)


async def _save_appointment(event, state: FSMContext, time_str: str):
    data = await state.get_data()
    order_id = data["sch_order_id"]
    date_str = data["sch_date"]

    selected = datetime.strptime(date_str, "%Y-%m-%d").date()
    if selected.weekday() == 6:
        if isinstance(event, CallbackQuery):
            await event.answer("⚪ Неділя — вихідний день.", show_alert=True)
        else:
            await event.answer("⚪ Неділя — вихідний день.")
        return

    # Фінальна перевірка безпосередньо перед записом.
    existing = await db.list_orders_by_date(event.from_user.id, date_str)
    # При зміні дати самого ж замовлення його запис треба ігнорувати.
    existing = [o for o in existing if o["id"] != order_id]
    if existing:
        text = "🔴 Цей день уже зайнятий. Оберіть інший."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    await db.set_appointment(order_id, date_str, time_str)
    await state.set_state(None)

    order = await db.get_order(order_id)
    text = (
        f"✅ Записано на ремонт: {_fmt_date(date_str)} о {time_str}\n"
        f"{_order_title(order)}"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text)
        await event.answer()
        target_message = event.message
    else:
        await event.answer(text)
        target_message = event

    from handlers.calculator import show_order_card
    await show_order_card(target_message, order_id)


# ================== РОЗКЛАД (перегляд усіх записів по днях) ==================

@router.message(F.text == "📅 Розклад")
async def show_schedule(message: Message):
    today = date.today()
    await _send_calendar(
        message,
        today.year,
        today.month,
        "viewcal",
        message.from_user.id,
    )


@router.callback_query(F.data.startswith("viewcalnav:"))
async def viewcal_nav(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    await _render_calendar(
        callback.message,
        int(year),
        int(month),
        "viewcal",
        callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(F.data == "viewcalcancel")
async def viewcal_cancel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data.startswith("viewcalbusy:"))
async def viewcal_busy(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    date_str = f"{year}-{month}-{day}"
    orders = await db.list_orders_by_date(callback.from_user.id, date_str)

    lines = [f"🔴 <b>Записи на {_fmt_date(date_str)}</b>", ""]
    if not orders:
        lines.append("Записів немає.")
    else:
        for o in orders:
            lines.append(f"🕐 {o['appointment_time']} — {_order_title(o)}")

    await callback.answer("\n".join(lines), show_alert=True)


@router.callback_query(F.data.startswith("viewcal:"))
async def viewcal_date_chosen(callback: CallbackQuery):
    _, year, month, day = callback.data.split(":")
    date_str = f"{year}-{month}-{day}"
    orders = await db.list_orders_by_date(callback.from_user.id, date_str)

    lines = [f"📅 <b>Записи на {_fmt_date(date_str)}</b>", ""]
    if not orders:
        lines.append("Записів немає.")
    else:
        for o in orders:
            lines.append(f"🕐 {o['appointment_time']} — {_order_title(o)}")

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = [
        [
            InlineKeyboardButton(
                text=f"#{o['id']} — {_order_title(o)}",
                callback_data=f"order_open:{o['id']}",
            )
        ]
        for o in orders
    ]
    rows.append([
        InlineKeyboardButton(
            text="⬅️ Назад до календаря",
            callback_data="schedule_back",
        )
    ])
    kb_markup = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=kb_markup,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "schedule_back")
async def schedule_back(callback: CallbackQuery):
    today = date.today()
    await _send_calendar(
        callback.message,
        today.year,
        today.month,
        "viewcal",
        callback.from_user.id,
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
