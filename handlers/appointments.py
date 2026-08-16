from datetime import date, datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
import keyboards as kb
import pricing
from states import ScheduleForm

router = Router()


# ---------- допоміжне ----------

def _fmt_date(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return d.strftime("%d.%m.%Y")


def _order_title(o: dict) -> str:
    return o["car_make"] or o["client_name"] or f"Замовлення #{o['id']}"


# ================== ЗАПИС НА РЕМОНТ (з картки замовлення) ==================

@router.callback_query(F.data.startswith("order_schedule:"))
async def order_schedule_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(sch_order_id=order_id)
    today = date.today()
    await callback.message.answer(
        "📅 Оберіть дату запису на ремонт:",
        reply_markup=kb.calendar_kb(today.year, today.month, "schcal"),
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
    await callback.message.edit_reply_markup(
        reply_markup=kb.calendar_kb(int(year), int(month), "schcal"),
    )
    await callback.answer()


@router.callback_query(F.data == "schcalcancel")
async def schcal_cancel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    await callback.message.delete()
    await callback.answer("Скасовано")


@router.callback_query(F.data.startswith("schcal:"))
async def schcal_date_chosen(callback: CallbackQuery, state: FSMContext):
    _, year, month, day = callback.data.split(":")
    date_str = f"{year}-{month}-{day}"
    await state.update_data(sch_date=date_str)
    await callback.message.edit_text(
        f"📅 Дата: {_fmt_date(date_str)}\n\nОберіть час:",
        reply_markup=kb.time_slots_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "schtime_back")
async def schtime_back(callback: CallbackQuery):
    today = date.today()
    await callback.message.edit_text(
        "📅 Оберіть дату запису на ремонт:",
        reply_markup=kb.calendar_kb(today.year, today.month, "schcal"),
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
    await message.answer(
        "📅 Розклад записів. Оберіть дату:",
        reply_markup=kb.calendar_kb(today.year, today.month, "viewcal"),
    )


@router.callback_query(F.data.startswith("viewcalnav:"))
async def viewcal_nav(callback: CallbackQuery):
    _, year, month = callback.data.split(":")
    await callback.message.edit_reply_markup(
        reply_markup=kb.calendar_kb(int(year), int(month), "viewcal"),
    )
    await callback.answer()


@router.callback_query(F.data == "viewcalcancel")
async def viewcal_cancel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()


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
    rows = [[InlineKeyboardButton(text=f"#{o['id']} — {_order_title(o)}", callback_data=f"order_open:{o['id']}")]
            for o in orders]
    rows.append([InlineKeyboardButton(text="⬅️ Назад до календаря", callback_data="schedule_back")])
    kb_markup = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text("\n".join(lines), reply_markup=kb_markup)
    await callback.answer()


@router.callback_query(F.data == "schedule_back")
async def schedule_back(callback: CallbackQuery):
    today = date.today()
    await callback.message.edit_text(
        "📅 Розклад записів. Оберіть дату:",
        reply_markup=kb.calendar_kb(today.year, today.month, "viewcal"),
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
