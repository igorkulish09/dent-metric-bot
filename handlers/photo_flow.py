"""
Гілка діалогу: користувач надсилає фото пошкодження, Claude Vision його аналізує.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import RepairForm
from keyboards import confirm_ai_kb, damage_types_kb, brands_kb
from price_data import DAMAGE_TYPES, DAMAGE_SIZE
from photo_analysis import analyze_damage_photo

router = Router()


@router.callback_query(RepairForm.choosing_mode, F.data == "mode_photo")
async def ask_for_photo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RepairForm.waiting_photo)
    await callback.message.answer(
        "📸 Надішліть, будь ласка, фото пошкодження (одним знімком, чітко та при "
        "гарному освітленні). Я проаналізую тип і приблизний розмір пошкодження."
    )
    await callback.answer()


@router.message(RepairForm.waiting_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext, bot: Bot):
    processing_msg = await message.answer("🔍 Аналізую фото, зачекайте кілька секунд...")

    # Беремо фото найкращої якості (останнє в списку розмірів)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes_io = await bot.download_file(file.file_path)
    image_bytes = file_bytes_io.read()

    result = analyze_damage_photo(image_bytes, media_type="image/jpeg")

    await state.update_data(
        damage_type=result["damage_type"],
        damage_size=result["damage_size"],
    )
    await state.set_state(RepairForm.confirming_ai_result)

    damage_label = DAMAGE_TYPES[result["damage_type"]]["label"]
    size_label = DAMAGE_SIZE[result["damage_size"]]["label"]

    await processing_msg.delete()
    await message.answer(
        f"🤖 Ось що я побачив на фото:\n\n"
        f"Тип пошкодження: <b>{damage_label}</b>\n"
        f"Приблизний розмір: <b>{size_label}</b>\n\n"
        f"💬 {result.get('description', '')}\n\n"
        f"Все правильно?",
        reply_markup=confirm_ai_kb(),
        parse_mode="HTML",
    )


@router.message(RepairForm.waiting_photo)
async def wrong_content_type(message: Message):
    await message.answer("Будь ласка, надішліть саме фото (як зображення, не файлом).")


@router.callback_query(RepairForm.confirming_ai_result, F.data == "ai_confirm")
async def ai_result_confirmed(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RepairForm.choosing_brand)
    await callback.message.answer(
        "Чудово! Тепер оберіть марку авто (або натисніть «Інша», щоб ввести вручну):",
        reply_markup=brands_kb(),
    )
    await callback.answer()


@router.callback_query(RepairForm.confirming_ai_result, F.data == "ai_correct")
async def ai_result_correct(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RepairForm.choosing_damage_type)
    await callback.message.answer(
        "Оберіть правильний тип пошкодження:",
        reply_markup=damage_types_kb(),
    )
    await callback.answer()
