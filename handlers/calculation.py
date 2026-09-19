"""
Гілка діалогу: вибір додаткових робіт (мульти-select), фінальний розрахунок
вартості та оформлення запису на діагностику.
"""
import json
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import RepairForm
from keyboards import extra_works_kb, contact_request_kb
from price_data import DAMAGE_TYPES, DAMAGE_SIZE, EXTRA_WORKS, calculate_price
from database import save_request
from config import ADMIN_IDS

router = Router()


# ---------- Toggle чекбоксу додаткової роботи ----------
@router.callback_query(RepairForm.choosing_extra_works, F.data.startswith("extra_"))
async def toggle_extra_work(callback: CallbackQuery, state: FSMContext):
    key = callback.data.removeprefix("extra_")
    data = await state.get_data()
    selected = set(data.get("extra_works", []))

    if key in selected:
        selected.remove(key)
    else:
        selected.add(key)

    await state.update_data(extra_works=list(selected))
    await callback.message.edit_reply_markup(reply_markup=extra_works_kb(selected))
    await callback.answer()


# ---------- Завершення вибору -> розрахунок ----------
@router.callback_query(RepairForm.choosing_extra_works, F.data == "extra_done")
async def finish_and_calculate(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    calc = calculate_price(
        brand=data["brand"],
        year=data["year"],
        damage_type=data["damage_type"],
        damage_size=data["damage_size"],
        extra_works=data.get("extra_works", []),
    )

    # Зберігаємо в БД
    request_id = await save_request(
        user_id=callback.from_user.id,
        username=callback.from_user.username or callback.from_user.full_name,
        brand=data["brand"],
        model=data["model"],
        year=data["year"],
        damage_type=data["damage_type"],
        damage_size=data["damage_size"],
        extra_works=json.dumps(data.get("extra_works", []), ensure_ascii=False),
        total_price=calc["total"],
    )
    await state.update_data(request_id=request_id, total_price=calc["total"])

    text = build_result_text(data, calc, request_id)
    await callback.message.answer(text, reply_markup=contact_request_kb(), parse_mode="HTML")
    await callback.answer()


def build_result_text(data: dict, calc: dict, request_id: int) -> str:
    damage_label = DAMAGE_TYPES[data["damage_type"]]["label"]
    size_label = DAMAGE_SIZE[data["damage_size"]]["label"]

    lines = [
        f"🧾 <b>Кошторис №{request_id}</b>",
        "",
        f"🚗 Авто: {data['brand']} {data['model']}, {data['year']} р.",
        f"🔧 Пошкодження: {damage_label}, {size_label}",
        "",
        f"Основні роботи: <b>{calc['main_work_price']} грн</b>",
    ]

    if calc["extras_detail"]:
        lines.append("\nДодаткові роботи:")
        for item in calc["extras_detail"]:
            lines.append(f"  • {item['label']} — {item['price']} грн")

    lines += [
        "",
        f"💰 <b>Разом орієнтовно: {calc['total']} грн</b>",
        "",
        "⚠️ Це попередня оцінка. Фінальна вартість підтверджується майстром "
        "після живого огляду авто.",
    ]
    return "\n".join(lines)


# ---------- Запис на діагностику ----------
@router.callback_query(F.data == "book_visit")
async def book_visit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RepairForm.entering_phone)
    await callback.message.answer(
        "Залиште, будь ласка, номер телефону — наш менеджер зв'яжеться з вами "
        "для узгодження часу діагностики:"
    )
    await callback.answer()


@router.message(RepairForm.entering_phone)
async def phone_entered(message: Message, state: FSMContext, bot: Bot):
    phone = message.text.strip()
    data = await state.get_data()

    await message.answer(
        f"✅ Дякуємо! Ваша заявка №{data.get('request_id', '—')} прийнята.\n"
        f"Ми зв'яжемося з вами за номером {phone} найближчим часом."
    )

    # Сповіщення адмінам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📩 Нова заявка №{data.get('request_id')}\n"
                f"Клієнт: @{message.from_user.username or message.from_user.full_name}\n"
                f"Телефон: {phone}\n"
                f"Авто: {data.get('brand')} {data.get('model')}, {data.get('year')}\n"
                f"Сума: {data.get('total_price')} грн",
            )
        except Exception:
            pass  # адмін міг не запускати бота — ігноруємо помилку

    await state.clear()
