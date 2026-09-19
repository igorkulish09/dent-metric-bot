from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from app.bot.keyboards.main import main_menu

router = Router()

@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 <b>Dent Metric</b>\n\nCRM для PDR-майстра.\n\nОберіть дію:",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
