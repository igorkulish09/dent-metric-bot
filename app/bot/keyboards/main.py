from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🚗 Нове замовлення"), KeyboardButton(text="📋 Замовлення")],
        [KeyboardButton(text="📅 Календар"), KeyboardButton(text="💰 Ціни")],
        [KeyboardButton(text="⚙️ Налаштування")],
    ], resize_keyboard=True)

def back_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
