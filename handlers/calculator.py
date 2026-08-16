from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import keyboards as kb
import pricing
import database as db
from states import OrderForm, DentForm

router = Router()


# ---------- "картка" розрахунку, яка сама оновлюється ----------
# Замість того щоб плодити купу однакових повідомлень (питання й вже
# обрані відповіді), ми ведемо ОДНЕ повідомлення: вже обрані пункти
# позначені ✅, а поточне питання — жирним із стрілкою 👉. Це не дає їм
# зливатися візуально.

def build_card_text(data: dict, next_question: str | None) -> str:
    lines = ["📝 <b>Розрахунок вм'ятини</b>", ""]

    if "element" in data:
        lines.append(f"✅ Елемент: {pricing.ELEMENTS[data['element']][0]}")
    if "technology" in data:
        lines.append(f"✅ Технологія: {pricing.TECHNOLOGY[data['technology']][0]}")
    if "complexity" in data:
        lines.append(f"✅ Складність: {pricing.COMPLEXITY[data['complexity']][0]}")
    if "material" in data:
        lines.append(f"✅ Матеріал: {pricing.MATERIAL[data['material']][0]}")
    if "car_class" in data:
        lines.append(f"✅ Клас авто: {pricing.CAR_CLASS[data['car_class']][0]}")
    if "width_cm" in data:
        lines.append(f"✅ Ширина: {data['width_cm']:g} см")

    if next_question:
        lines.append("")
        lines.append(f"👉 <b>{next_question}</b>")

    return "\n".join(lines)


async def update_card(state: FSMContext, next_question: str, reply_markup=None,
                       callback: CallbackQuery | None = None, bot: Bot | None = None):
    """Редагує єдину картку розрахунку. Якщо прийшли через callback — редагуємо
    те саме повідомлення напряму. Якщо прийшли через текстове повідомлення
    (крок ширини/довжини) — редагуємо картку за збереженими chat_id/message_id."""
    data = await state.get_data()
    text = build_card_text(data, next_question)

    if callback is not None:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    else:
        await bot.edit_message_text(
            text,
            chat_id=data["card_chat_id"],
            message_id=data["card_message_id"],
            reply_markup=reply_markup,
        )


# ---------- почати новий розрахунок ----------

@router.message(F.text == "🧮 Новий розрахунок")
async def start_calculation(message: Message, state: FSMContext):
    order_id = await db.create_order(message.from_user.id)
    await state.update_data(order_id=order_id, new_order=True)
    await state.set_state(DentForm.element)

    # окреме повідомлення тримає кнопку "Скасувати" на клавіатурі внизу
    await message.answer("Починаємо новий розрахунок 👇", reply_markup=kb.cancel_kb())

    card = await message.answer(
        build_card_text({}, "Оберіть пошкоджений елемент:"),
        reply_markup=kb.element_kb(),
    )
    await state.update_data(card_chat_id=card.chat.id, card_message_id=card.message_id)


# ---------- крок 1: елемент ----------

@router.callback_query(DentForm.element, F.data.startswith("elem:"))
async def dent_element_chosen(callback: CallbackQuery, state: FSMContext):
    element = callback.data.split(":", 1)[1]
    await state.update_data(element=element)
    await state.set_state(DentForm.technology)
    data = await state.get_data()
    await callback.message.edit_text(
        build_card_text(data, "Технологія ремонту:"),
        reply_markup=kb.technology_kb(),
    )
    await callback.answer()


# ---------- крок 2: технологія ----------

@router.callback_query(DentForm.technology, F.data.startswith("tech:"))
async def dent_technology_chosen(callback: CallbackQuery, state: FSMContext):
    technology = callback.data.split(":", 1)[1]
    await state.update_data(technology=technology)
    await state.set_state(DentForm.complexity)
    data = await state.get_data()
    await callback.message.edit_text(
        build_card_text(data, "Складність пошкодження:"),
        reply_markup=kb.complexity_kb(),
    )
    await callback.answer()


# ---------- крок 3: складність ----------

@router.callback_query(DentForm.complexity, F.data.startswith("cplx:"))
async def dent_complexity_chosen(callback: CallbackQuery, state: FSMContext):
    complexity = callback.data.split(":", 1)[1]
    await state.update_data(complexity=complexity)
    await state.set_state(DentForm.material)
    data = await state.get_data()
    await callback.message.edit_text(
        build_card_text(data, "Матеріал панелі:"),
        reply_markup=kb.material_kb(),
    )
    await callback.answer()


# ---------- крок 4: матеріал ----------

@router.callback_query(DentForm.material, F.data.startswith("mtrl:"))
async def dent_material_chosen(callback: CallbackQuery, state: FSMContext):
    material = callback.data.split(":", 1)[1]
    await state.update_data(material=material)
    await state.set_state(DentForm.car_class)
    data = await state.get_data()
    await callback.message.edit_text(
        build_card_text(data, "Клас автомобіля:"),
        reply_markup=kb.car_class_kb(),
    )
    await callback.answer()


# ---------- крок 5: клас авто ----------

@router.callback_query(DentForm.car_class, F.data.startswith("clss:"))
async def dent_class_chosen(callback: CallbackQuery, state: FSMContext):
    car_class = callback.data.split(":", 1)[1]
    await state.update_data(car_class=car_class)
    await state.set_state(DentForm.width)
    data = await state.get_data()
    await callback.message.edit_text(
        build_card_text(data, "Введіть ширину вм'ятини, см (число, напр. 5):"),
        reply_markup=None,
    )
    await callback.answer()


# ---------- крок 6-7: розмір вм'ятини ----------

@router.message(DentForm.width)
async def dent_width_entered(message: Message, state: FSMContext, bot: Bot):
    try:
        width = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Введіть, будь ласка, число. Наприклад: 5 або 5.5")
        return
    await state.update_data(width_cm=width)
    await state.set_state(DentForm.length)
    await message.delete()
    await update_card(state, "Введіть довжину вм'ятини, см (число, напр. 3):", bot=bot)


@router.message(DentForm.length)
async def dent_length_entered(message: Message, state: FSMContext, bot: Bot):
    try:
        length = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Введіть, будь ласка, число. Наприклад: 3 або 3.5")
        return
    await message.delete()

    data = await state.get_data()
    element = data["element"]
    technology = data["technology"]
    complexity = data["complexity"]
    material = data["material"]
    car_class = data["car_class"]
    width = data["width_cm"]
    order_id = data["order_id"]

    price = pricing.calc_price(element, technology, complexity, material, car_class)
    await db.add_dent(order_id, element, technology, complexity, material, car_class, price,
                       width_cm=width, length_cm=length)

    total = await db.order_total(order_id)
    data["length_cm"] = length
    final_text = build_card_text(data, None) + f"\n✅ Довжина: {length:g} см\n\n" \
        f"💰 <b>Вм'ятину додано! Разом по замовленню: {total} грн</b>"

    await bot.edit_message_text(
        final_text,
        chat_id=data["card_chat_id"],
        message_id=data["card_message_id"],
        reply_markup=kb.dent_added_kb(),
    )
    await state.set_state(None)


# ---------- додати ще / завершити ----------

@router.callback_query(F.data == "dent_more")
async def dent_more(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DentForm.element)
    card = await callback.message.answer(
        build_card_text({}, "Оберіть пошкоджений елемент:"),
        reply_markup=kb.element_kb(),
    )
    # скидаємо накопичені дані попередньої вм'ятини, лишаємо order_id
    data = await state.get_data()
    await state.update_data(
        order_id=data["order_id"], new_order=data.get("new_order", False),
        card_chat_id=card.chat.id, card_message_id=card.message_id,
    )
    await callback.answer()


@router.callback_query(F.data == "dent_finish")
async def dent_finish(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    order = await db.get_order(order_id)
    await callback.answer()

    if order["status"] == "in_progress":
        # це вже існуюче замовлення в журналі — просто показуємо картку
        await show_order_card(callback.message, order_id)
        await state.clear()
        return

    # нове замовлення — питаємо дані клієнта й авто, щоб зберегти в журнал
    await state.set_state(OrderForm.client_name)
    await callback.message.answer(
        "Тепер додамо дані для журналу й акту.\n\n👤 Ім'я клієнта:",
        reply_markup=kb.skip_cancel_kb(),
    )


# ---------- анкета клієнта/авто ----------

@router.message(OrderForm.client_name)
async def get_client_name(message: Message, state: FSMContext):
    value = "" if message.text == "➡️ Пропустити" else message.text
    await state.update_data(client_name=value)
    await state.set_state(OrderForm.client_phone)
    await message.answer("📞 Телефон клієнта:", reply_markup=kb.skip_cancel_kb())


@router.message(OrderForm.client_phone)
async def get_client_phone(message: Message, state: FSMContext):
    value = "" if message.text == "➡️ Пропустити" else message.text
    await state.update_data(client_phone=value)
    await state.set_state(OrderForm.car_make)
    await message.answer("🚗 Марка авто:", reply_markup=kb.skip_cancel_kb())


@router.message(OrderForm.car_make)
async def get_car_make(message: Message, state: FSMContext):
    value = "" if message.text == "➡️ Пропустити" else message.text
    await state.update_data(car_make=value)
    await state.set_state(OrderForm.car_model)
    await message.answer("Модель авто:", reply_markup=kb.skip_cancel_kb())


@router.message(OrderForm.car_model)
async def get_car_model(message: Message, state: FSMContext):
    value = "" if message.text == "➡️ Пропустити" else message.text
    await state.update_data(car_model=value)
    await state.set_state(OrderForm.car_plate)
    await message.answer("Держномер:", reply_markup=kb.skip_cancel_kb())


@router.message(OrderForm.car_plate)
async def get_car_plate(message: Message, state: FSMContext):
    value = "" if message.text == "➡️ Пропустити" else message.text
    await state.update_data(car_plate=value)
    data = await state.get_data()
    order_id = data["order_id"]

    for field in ("client_name", "client_phone", "car_make", "car_model", "car_plate"):
        await db.update_order_field(order_id, field, data.get(field, ""))
    await db.update_order_field(order_id, "status", "in_progress")

    await state.clear()
    await message.answer("✅ Замовлення збережено в журнал!", reply_markup=kb.main_menu())
    await show_order_card(message, order_id)


# ---------- показ картки замовлення (перевикористовується) ----------

async def show_order_card(message: Message, order_id: int):
    order = await db.get_order(order_id)
    dents = await db.list_dents(order_id)
    total = sum(d["price"] for d in dents)

    lines = [f"📋 <b>Замовлення #{order_id}</b>"]
    if order["car_make"]:
        lines.append(f"🚗 {order['car_make']} {order['car_model']} {order['car_plate']}".strip())
    if order["client_name"]:
        client = order["client_name"]
        if order["client_phone"]:
            client += f", {order['client_phone']}"
        lines.append(f"👤 {client}")
    status_map = {"draft": "чернетка", "in_progress": "в роботі", "completed": "завершено"}
    lines.append(f"Статус: {status_map.get(order['status'], order['status'])}")
    if order.get("appointment_date"):
        from datetime import datetime as _dt
        d = _dt.strptime(order["appointment_date"], "%Y-%m-%d").strftime("%d.%m.%Y")
        lines.append(f"📅 Запис: {d} о {order['appointment_time']}")
    lines.append("")

    if dents:
        for i, d in enumerate(dents, start=1):
            elem = pricing.ELEMENTS[d["element"]][0]
            width = d.get("width_cm") or 0
            length = d.get("length_cm") or 0
            size = f", {width:g}×{length:g} см" if (width or length) else ""
            lines.append(f"{i}. {elem}{size} — {d['price']} грн")
    else:
        lines.append("Вм'ятин ще немає.")

    lines.append("")
    lines.append(f"💰 Разом: {total} грн")

    await message.answer("\n".join(lines), reply_markup=kb.order_card_kb(
        order_id, order["status"], has_appointment=bool(order.get("appointment_date")),
    ))
