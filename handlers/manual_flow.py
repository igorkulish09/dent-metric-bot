"""
Гілка діалогу: марка/модель/рік авто + ручний вибір типу й розміру пошкодження.
Використовується як після ручного режиму, так і як "виправлення" після фото-аналізу.
"""
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import RepairForm
from keyboards import brands_kb, damage_types_kb, damage_size_kb, extra_works_kb

router = Router()


# ---------- Вибір режиму: вручну ----------
@router.callback_query(RepairForm.choosing_mode, F.data == "mode_manual")
async def start_manual_mode(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RepairForm.choosing_brand)
    await callback.message.answer(
        "Оберіть марку авто (або натисніть «Інша», щоб ввести вручну):",
        reply_markup=brands_kb(),
    )
    await callback.answer()


# ---------- Марка ----------
@router.callback_query(RepairForm.choosing_brand, F.data.startswith("brand_"))
async def brand_chosen(callback: CallbackQuery, state: FSMContext):
    brand = callback.data.removeprefix("brand_")
    if brand == "Інша":
        await state.set_state(RepairForm.entering_brand_manual)
        await callback.message.answer("Введіть марку авто текстом:")
        await callback.answer()
        return

    await state.update_data(brand=brand)
    await state.set_state(RepairForm.entering_model)
    await callback.message.answer(f"Марка: <b>{brand}</b>\n\nТепер введіть модель авто:", parse_mode="HTML")
    await callback.answer()


@router.message(RepairForm.entering_brand_manual)
async def brand_entered_manual(message: Message, state: FSMContext):
    await state.update_data(brand=message.text.strip())
    await state.set_state(RepairForm.entering_model)
    await message.answer("Тепер введіть модель авто:")


# ---------- Модель ----------
@router.message(RepairForm.entering_model)
async def model_entered(message: Message, state: FSMContext):
    await state.update_data(model=message.text.strip())
    await state.set_state(RepairForm.entering_year)
    await message.answer("Введіть рік випуску авто (наприклад, 2018):")


# ---------- Рік ----------
@router.message(RepairForm.entering_year)
async def year_entered(message: Message, state: FSMContext):
    text = message.text.strip()
    current_year = date.today().year

    if not text.isdigit() or not (1970 <= int(text) <= current_year + 1):
        await message.answer(
            f"Будь ласка, введіть коректний рік числом (1970–{current_year})."
        )
        return

    await state.update_data(year=int(text))

    data = await state.get_data()
    if data.get("damage_type"):
        # Тип/розмір вже визначені по фото — одразу переходимо до додаткових робіт
        await state.set_state(RepairForm.choosing_extra_works)
        await state.update_data(extra_works=[])
        await message.answer(
            "Оберіть додаткові роботи (можна декілька) або одразу натисніть «Готово»:",
            reply_markup=extra_works_kb(set()),
        )
    else:
        await state.set_state(RepairForm.choosing_damage_type)
        await message.answer(
            "Який тип пошкодження?",
            reply_markup=damage_types_kb(),
        )


# ---------- Тип пошкодження (ручний вибір) ----------
@router.callback_query(RepairForm.choosing_damage_type, F.data.startswith("dmg_"))
async def damage_type_chosen(callback: CallbackQuery, state: FSMContext):
    damage_type = callback.data.removeprefix("dmg_")
    await state.update_data(damage_type=damage_type)
    await state.set_state(RepairForm.choosing_damage_size)
    await callback.message.answer(
        "Який приблизний розмір пошкодження?",
        reply_markup=damage_size_kb(),
    )
    await callback.answer()


# ---------- Розмір пошкодження ----------
@router.callback_query(RepairForm.choosing_damage_size, F.data.startswith("size_"))
async def damage_size_chosen(callback: CallbackQuery, state: FSMContext):
    damage_size = callback.data.removeprefix("size_")
    await state.update_data(damage_size=damage_size)

    data = await state.get_data()
    if not data.get("brand"):
        # Це гілка "виправити після фото" — авто ще не вводили
        await state.set_state(RepairForm.choosing_brand)
        await callback.message.answer(
            "Тепер оберіть марку авто (або «Інша» для ручного вводу):",
            reply_markup=brands_kb(),
        )
    else:
        await state.set_state(RepairForm.choosing_extra_works)
        await state.update_data(extra_works=[])
        await callback.message.answer(
            "Оберіть додаткові роботи (можна декілька) або одразу натисніть «Готово»:",
            reply_markup=extra_works_kb(set()),
        )
    await callback.answer()
