from datetime import date, timedelta
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from app.bot.states.order import BookingState
from app.database.models import Booking, Order, Car
from app.database.session import SessionLocal

router = Router()
MONTHS = ['Січень','Лютий','Березень','Квітень','Травень','Червень','Липень','Серпень','Вересень','Жовтень','Листопад','Грудень']
WEEKDAYS = ['Пн','Вт','Ср','Чт','Пт','Сб','Нд']


def shift_month(year, month, delta):
    n = year * 12 + month - 1 + delta
    return n // 12, n % 12 + 1


def days_in_month(year, month):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    result = []
    d = start
    while d < end:
        result.append(d)
        d += timedelta(days=1)
    return result


def booking_dates(start, days):
    result, d = [], start
    while len(result) < max(1, days):
        if d.weekday() != 6:
            result.append(d)
        d += timedelta(days=1)
    return result


async def all_occupied():
    async with SessionLocal() as session:
        bookings = (await session.scalars(select(Booking))).all()
    occupied = {}
    for b in bookings:
        for d in booking_dates(b.work_date, b.days):
            occupied.setdefault(d, []).append(b.order_id)
    return occupied


def day_button(d, occupied):
    if d.weekday() == 6:
        return InlineKeyboardButton(text=f'⚪{d.day}', callback_data='cal:noop')
    if d in occupied:
        return InlineKeyboardButton(text=f'🔴{d.day}', callback_data=f'cal:day:{d.isoformat()}')
    return InlineKeyboardButton(text=f'🟢{d.day}', callback_data=f'cal:day:{d.isoformat()}')


def calendar_keyboard(year, month, occupied):
    py, pm = shift_month(year, month, -1)
    ny, nm = shift_month(year, month, 1)
    rows = [[
        InlineKeyboardButton(text='‹', callback_data=f'cal:{py}:{pm}'),
        InlineKeyboardButton(text=f'{MONTHS[month-1]} {year}', callback_data='cal:noop'),
        InlineKeyboardButton(text='›', callback_data=f'cal:{ny}:{nm}')
    ]]
    rows.append([InlineKeyboardButton(text=x, callback_data='cal:noop') for x in WEEKDAYS])
    week = [None] * date(year, month, 1).weekday()
    for d in days_in_month(year, month):
        week.append(d)
        if len(week) == 7:
            rows.append([day_button(x, occupied) if x else InlineKeyboardButton(text=' ', callback_data='cal:noop') for x in week])
            week = []
    if week:
        week += [None] * (7-len(week))
        rows.append([day_button(x, occupied) if x else InlineKeyboardButton(text=' ', callback_data='cal:noop') for x in week])
    rows.append([
        InlineKeyboardButton(text='🟢 Вільно', callback_data='cal:noop'),
        InlineKeyboardButton(text='🔴 Зайнято', callback_data='cal:noop'),
        InlineKeyboardButton(text='⚪ Неділя', callback_data='cal:noop')
    ])
    rows.append([InlineKeyboardButton(text='➕ Забронювати', callback_data='cal:book')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def render_calendar(target, year, month):
    occupied = await all_occupied()
    text = f'📅 <b>{MONTHS[month-1]} {year}</b>\n\n🟢 Вільно   🔴 Зайнято   ⚪ Неділя\nНатисніть на день, щоб переглянути завантаження.'
    kb = calendar_keyboard(year, month, occupied)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    else:
        await target.answer(text, reply_markup=kb, parse_mode='HTML')


@router.message(F.text == '📅 Календар')
async def calendar(message: Message):
    today = date.today()
    await render_calendar(message, today.year, today.month)


@router.callback_query(F.data.startswith('cal:'))
async def calendar_callback(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(':')
    if parts[1] == 'noop':
        await call.answer(); return
    if parts[1] == 'book':
        async with SessionLocal() as session:
            orders = (await session.scalars(select(Order).order_by(Order.id.desc()).limit(30))).all()
            rows = []
            for o in orders:
                car = await session.get(Car, o.car_id)
                rows.append([InlineKeyboardButton(text=f'#{o.id} {car.brand} {car.model} {car.plate}', callback_data=f'bookorder:{o.id}')])
        if not rows:
            await call.message.answer('Спочатку створіть замовлення.')
        else:
            await call.message.answer('Оберіть замовлення для бронювання:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        await call.answer(); return
    if parts[1] == 'day':
        selected = date.fromisoformat(parts[2])
        if selected.weekday() == 6:
            await call.answer('Неділя — вихідний день.', show_alert=True); return
        occupied = await all_occupied()
        order_ids = occupied.get(selected, [])
        if not order_ids:
            await call.answer('🟢 Вільно', show_alert=True); return
        async with SessionLocal() as session:
            lines = []
            for oid in order_ids:
                o = await session.get(Order, oid)
                car = await session.get(Car, o.car_id)
                lines.append(f'#{o.id} — {car.brand} {car.model} {car.plate}')
        await call.answer('🔴 Зайнято:\n' + '\n'.join(lines), show_alert=True); return
    if len(parts) == 3:
        await render_calendar(call, int(parts[1]), int(parts[2]))
        await call.answer()


@router.callback_query(F.data.startswith('bookorder:'))
async def booking_order(call: CallbackQuery, state: FSMContext):
    oid = int(call.data.split(':')[1])
    await state.set_state(BookingState.date)
    await state.update_data(order_id=oid)
    occupied = await all_occupied()
    today = date.today()
    rows = []
    for i in range(60):
        d = today + timedelta(days=i)
        if d.weekday() == 6:
            continue
        if d in occupied:
            rows.append([InlineKeyboardButton(text=f'🔴 {d:%d.%m}', callback_data='cal:noop')])
        else:
            rows.append([InlineKeyboardButton(text=f'🟢 {d:%d.%m}', callback_data=f'bookdate:{d.isoformat()}')])
    await call.message.answer('Оберіть вільну дату початку:', reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(BookingState.date, F.data.startswith('bookdate:'))
async def booking_date(call: CallbackQuery, state: FSMContext):
    await state.update_data(date=call.data.split(':')[1])
    await state.set_state(BookingState.days)
    await call.message.answer('Скільки робочих днів? 1–30')
    await call.answer()


@router.message(BookingState.days)
async def booking_days(message: Message, state: FSMContext):
    try:
        days = int(message.text); assert 1 <= days <= 30
    except Exception:
        await message.answer('Введіть число 1–30.'); return
    data = await state.get_data()
    dates = booking_dates(date.fromisoformat(data['date']), days)
    occupied = await all_occupied()
    conflicts = [d for d in dates if d in occupied]
    if conflicts:
        await message.answer('❌ Деякі дати вже зайняті:\n' + ', '.join(d.strftime('%d.%m.%Y') for d in conflicts)); return
    async with SessionLocal() as session:
        order = await session.get(Order, data['order_id'])
        if not order:
            await message.answer('Замовлення не знайдено.'); await state.clear(); return
        session.add(Booking(order_id=order.id, work_date=dates[0], days=days))
        order.status = 'planned'
        await session.commit()
    await state.clear()
    await message.answer('✅ Заброньовано:\n' + '\n'.join(f'🔴 {d:%d.%m.%Y}' for d in dates))
