from decimal import Decimal
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from app.bot.keyboards.main import main_menu
from app.bot.states.order import OrderState, PaymentState
from app.database.models import User, Car, Order, Dent, DentFactor, Payment
from app.database.session import SessionLocal
from app.services.pricing import get_price

router = Router()
ELEMENTS = ["Передній бампер","Задній бампер","Переднє крило","Заднє крило","Передні двері","Задні двері","Капот","Кришка багажника","Стійка даху","Поріг","Дах","Інше"]
COMPLEXITIES = ["Середня","Висока"]
MATERIALS = ["Сталь","Алюміній","Пластик"]
FACTORS = [
("scratch","Вм'ятина з царапиною"),("chip","З маленьким сколом"),
("stiffness","Вм'ятина над жорсткістю"),("outline_stiffness","Обрисувало жорсткість"),
("geometry","Повело геометрію"),("cracked_metal","Лопнув метал"),
("edge","Вм'ятина на ребрі"),("bad_access","Поганий доступ"),
("save_replacement","Рятуємо деталь від заміни"),("rework_x3","Переробка після другого майстра ×3"),
("disassembly","Обов'язковий розбір / зняття деталі"),("hard_stretch","Жорстка розтяжка")]

def buttons(items, prefix):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x, callback_data=f"{prefix}:{i}")] for i,x in enumerate(items)])

def factor_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"factor:{i}")] for i,(_,name) in enumerate(FACTORS)] + [[InlineKeyboardButton(text="✅ Завершити вм'ятину", callback_data="factor:finish")]])

def calc(data):
    base=Decimal(str(data.get("base_price",0)))
    surcharge=sum((Decimal(str(x["surcharge"])) for x in data.get("current_factors",[])), Decimal("0"))
    return base, surcharge, base+surcharge

@router.message(F.text == "🚗 Нове замовлення")
async def new_order(message: Message, state: FSMContext):
    await state.clear(); await state.set_state(OrderState.customer); await message.answer("Введіть ім'я замовника:")

@router.message(OrderState.customer)
async def customer(message: Message,state:FSMContext): await state.update_data(customer=message.text.strip()); await state.set_state(OrderState.brand); await message.answer("Марка автомобіля:")
@router.message(OrderState.brand)
async def brand(message: Message,state:FSMContext): await state.update_data(brand=message.text.strip()); await state.set_state(OrderState.model); await message.answer("Модель:")
@router.message(OrderState.model)
async def model(message: Message,state:FSMContext): await state.update_data(model=message.text.strip()); await state.set_state(OrderState.plate); await message.answer("Державний номер:")
@router.message(OrderState.plate)
async def plate(message: Message,state:FSMContext): await state.update_data(plate=message.text.strip().upper()); await state.set_state(OrderState.car_class); await message.answer("Клас авто:",reply_markup=buttons(["Стандарт","Преміум"],"class"))

@router.callback_query(OrderState.car_class,F.data.startswith("class:"))
async def car_class(call:CallbackQuery,state:FSMContext):
    await state.update_data(car_class=["Стандарт","Преміум"][int(call.data.split(":")[1])]); await state.set_state(OrderState.dent_photo); await call.message.edit_text("Вм'ятина №1: надішліть фото або напишіть «пропустити»."); await call.answer()

@router.message(OrderState.dent_photo,F.photo)
async def dent_photo(message:Message,state:FSMContext): await state.update_data(photo=message.photo[-1].file_id); await state.set_state(OrderState.dent_size); await message.answer("Розмір вм'ятини у см, наприклад 15:")
@router.message(OrderState.dent_photo)
async def dent_photo_skip(message:Message,state:FSMContext):
    if message.text and message.text.lower() in ("пропустити","пропуск","skip"):
        await state.update_data(photo=None); await state.set_state(OrderState.dent_size); await message.answer("Розмір вм'ятини у см, наприклад 15:")
    else: await message.answer("Надішліть фото або напишіть «пропустити».")

@router.message(OrderState.dent_size)
async def dent_size(message:Message,state:FSMContext):
    try: size=Decimal(message.text.replace(",",".")); assert size>0
    except Exception: await message.answer("Введіть число, наприклад 15."); return
    await state.update_data(size=size); await state.set_state(OrderState.dent_element); await message.answer("Пошкоджений елемент:",reply_markup=buttons(ELEMENTS,"element"))
@router.callback_query(OrderState.dent_element,F.data.startswith("element:"))
async def dent_element(call:CallbackQuery,state:FSMContext): await state.update_data(element=ELEMENTS[int(call.data.split(":")[1])]); await state.set_state(OrderState.dent_technology); await call.message.edit_text("Технологія:",reply_markup=buttons(["Без фарбування (PDR)"],"tech")); await call.answer()
@router.callback_query(OrderState.dent_technology,F.data.startswith("tech:"))
async def dent_technology(call:CallbackQuery,state:FSMContext): await state.update_data(technology="Без фарбування (PDR)"); await state.set_state(OrderState.dent_complexity); await call.message.edit_text("Складність:",reply_markup=buttons(COMPLEXITIES,"complexity")); await call.answer()
@router.callback_query(OrderState.dent_complexity,F.data.startswith("complexity:"))
async def dent_complexity(call:CallbackQuery,state:FSMContext): await state.update_data(complexity=COMPLEXITIES[int(call.data.split(":")[1])]); await state.set_state(OrderState.dent_material); await call.message.edit_text("Матеріал:",reply_markup=buttons(MATERIALS,"material")); await call.answer()

@router.callback_query(OrderState.dent_material,F.data.startswith("material:"))
async def dent_material(call:CallbackQuery,state:FSMContext):
    await state.update_data(material=MATERIALS[int(call.data.split(":")[1])])
    data=await state.get_data(); base=await get_price(data["element"],data["technology"],data["complexity"],data["material"],data["car_class"])
    await state.update_data(base_price=base,current_factors=[]); await state.set_state(OrderState.factor)
    await call.message.edit_text(f"💰 Базова ціна: {base} грн\n\nОберіть фактор. Після кожного фактора введіть доплату.",reply_markup=factor_keyboard()); await call.answer()

@router.callback_query(OrderState.factor,F.data.startswith("factor:"))
async def factor_select(call:CallbackQuery,state:FSMContext):
    value=call.data.split(":")[1]
    if value=="finish":
        data=await state.get_data(); base,sur,total=calc(data); await state.update_data(total_price=total); await state.set_state(OrderState.finish)
        await call.message.edit_text(f"🧾 <b>Вм'ятина</b>\nБаза: {base} грн\nДоплати: {sur} грн\n<b>Разом: {total} грн</b>\n\nДодати ще вм'ятину?",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Додати ще",callback_data="dent:add"),InlineKeyboardButton(text="✅ Завершити",callback_data="dent:finish")]]))
    else:
        code,name=FACTORS[int(value)]; await state.update_data(pending_factor={"code":code,"name":name}); await state.set_state(OrderState.factor_price); await call.message.answer(f"➕ <b>{name}</b>\nВведіть доплату в грн (якщо 0 — введіть 0):",parse_mode="HTML")
    await call.answer()

@router.message(OrderState.factor_price)
async def factor_price(message:Message,state:FSMContext):
    try: amount=Decimal(message.text.replace(",",".")); assert amount>=0
    except Exception: await message.answer("Введіть число, наприклад 500."); return
    data=await state.get_data(); factors=data.get("current_factors",[]); pf=data["pending_factor"]
    factors.append({"code":pf["code"],"name":pf["name"],"surcharge":str(amount)})
    await state.update_data(current_factors=factors); base,sur,total=calc({**data,"current_factors":factors}); await state.set_state(OrderState.factor)
    await message.answer(f"✅ {pf['name']}: +{amount} грн\nБаза: {base} грн\nДоплати: {sur} грн\n💰 <b>Поточна ціна: {total} грн</b>",reply_markup=factor_keyboard(),parse_mode="HTML")

@router.callback_query(OrderState.finish,F.data=="dent:add")
async def add_dent(call:CallbackQuery,state:FSMContext):
    data=await state.get_data(); dents=data.get("draft_dents",[]); dents.append({k:data.get(k) for k in ["photo","size","element","technology","complexity","material","base_price","total_price","current_factors"]}); await state.update_data(draft_dents=dents); await state.set_state(OrderState.dent_photo); await call.message.edit_text(f"Вм'ятина №{len(dents)+1}: фото або «пропустити»."); await call.answer()

@router.callback_query(OrderState.finish,F.data=="dent:finish")
async def finish_order(call:CallbackQuery,state:FSMContext):
    data=await state.get_data(); dents=data.get("draft_dents",[]); dents.append({k:data.get(k) for k in ["photo","size","element","technology","complexity","material","base_price","total_price","current_factors"]})
    async with SessionLocal() as session:
        user=await session.scalar(select(User).where(User.telegram_id==call.from_user.id))
        if not user: user=User(telegram_id=call.from_user.id,username=call.from_user.username,first_name=call.from_user.first_name); session.add(user); await session.flush()
        car=Car(brand=data["brand"],model=data["model"],plate=data["plate"],car_class=data["car_class"]); session.add(car); await session.flush()
        order=Order(user_id=user.id,car_id=car.id,customer_name=data["customer"]); session.add(order); await session.flush(); total=Decimal("0")
        for i,d in enumerate(dents,1):
            dent=Dent(order_id=order.id,number=i,photo_file_id=d["photo"],size_cm=d["size"],element=d["element"],technology=d["technology"],complexity=d["complexity"],material=d["material"],base_price=d["base_price"],total_price=d["total_price"]); session.add(dent); await session.flush(); total+=Decimal(str(d["total_price"]))
            for f in d.get("current_factors",[]): session.add(DentFactor(dent_id=dent.id,code=f["code"],name=f["name"],surcharge=Decimal(f["surcharge"])))
        order.total=total; await session.commit(); oid=order.id
    await state.clear(); await call.message.answer(f"✅ Замовлення #{oid} створено.\n💰 Загальна сума: {total} грн",reply_markup=main_menu()); await call.answer()

@router.message(F.text=="📋 Замовлення")
async def orders_list(message:Message):
    async with SessionLocal() as session: orders=(await session.scalars(select(Order).order_by(Order.id.desc()).limit(30))).all()
    if not orders: await message.answer("Замовлень поки немає."); return
    await message.answer("📋 Замовлення:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"#{o.id} — {o.total} грн — {o.status}",callback_data=f"order:{o.id}")] for o in orders]))

@router.callback_query(F.data.startswith("order:"))
async def order_view(call:CallbackQuery):
    oid=int(call.data.split(":")[1])
    async with SessionLocal() as session:
        order=await session.get(Order,oid); car=await session.get(Car,order.car_id); dents=(await session.scalars(select(Dent).where(Dent.order_id==oid).order_by(Dent.number))).all(); paid=await session.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.order_id==oid))
    text=f"🚗 <b>Замовлення #{oid}</b>\n{car.brand} {car.model} — {car.plate}\n\n"+"".join(f"#{d.number} {d.element}: {d.total_price} грн\n" for d in dents)+f"\n💰 Разом: {order.total} грн\nОплачено: {paid} грн\nЗалишок: {Decimal(order.total)-Decimal(paid)} грн"
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💵 Додати оплату",callback_data=f"pay:{oid}")],[InlineKeyboardButton(text="📄 Акт",callback_data=f"act:{oid}")],[InlineKeyboardButton(text="🗑 Видалити вм'ятину",callback_data=f"deldent:{oid}")],[InlineKeyboardButton(text="🔄 Статус",callback_data=f"status:{oid}")]])
    await call.message.edit_text(text,reply_markup=kb,parse_mode="HTML"); await call.answer()

@router.callback_query(F.data.startswith("deldent:"))
async def delete_dent_menu(call:CallbackQuery):
    oid=int(call.data.split(":")[1])
    async with SessionLocal() as session: dents=(await session.scalars(select(Dent).where(Dent.order_id==oid).order_by(Dent.number))).all()
    await call.message.answer("Оберіть вм'ятину:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"🗑 #{d.number} {d.element} — {d.total_price} грн",callback_data=f"delone:{d.id}")] for d in dents])); await call.answer()

@router.callback_query(F.data.startswith("delone:"))
async def delete_dent(call:CallbackQuery):
    did=int(call.data.split(":")[1])
    async with SessionLocal() as session:
        dent=await session.get(Dent,did); oid=dent.order_id; session.delete(dent); await session.flush(); dents=(await session.scalars(select(Dent).where(Dent.order_id==oid).order_by(Dent.id))).all()
        for i,d in enumerate(dents,1): d.number=i
        order=await session.get(Order,oid); order.total=sum((Decimal(str(d.total_price)) for d in dents),Decimal("0")); await session.commit()
    await call.message.answer(f"✅ Видалено. Нова сума: {order.total} грн"); await call.answer()

@router.callback_query(F.data.startswith("status:"))
async def status_menu(call:CallbackQuery):
    oid=int(call.data.split(":")[1]); statuses=[("new","Нове"),("planned","Заплановано"),("in_work","В роботі"),("done","Виконано"),("paid","Оплачено")]
    await call.message.answer("Оберіть статус:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label,callback_data=f"setstatus:{oid}:{key}")] for key,label in statuses])); await call.answer()
@router.callback_query(F.data.startswith("setstatus:"))
async def set_status(call:CallbackQuery):
    _,oid,status=call.data.split(":")
    async with SessionLocal() as session: order=await session.get(Order,int(oid)); order.status=status; await session.commit()
    await call.message.answer(f"✅ Статус #{oid}: {status}"); await call.answer()

@router.callback_query(F.data.startswith("pay:"))
async def payment_start(call:CallbackQuery,state:FSMContext): await state.set_state(PaymentState.amount); await state.update_data(order_id=int(call.data.split(":")[1])); await call.message.answer("Введіть суму оплати, грн:"); await call.answer()
@router.message(PaymentState.amount)
async def payment_save(message:Message,state:FSMContext):
    try: amount=Decimal(message.text.replace(",",".")); assert amount>0
    except Exception: await message.answer("Введіть додатне число."); return
    data=await state.get_data()
    async with SessionLocal() as session: session.add(Payment(order_id=data["order_id"],amount=amount)); await session.commit()
    await state.clear(); await message.answer(f"✅ Оплату {amount} грн додано.",reply_markup=main_menu())
