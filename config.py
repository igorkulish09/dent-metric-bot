"""
Конфігурація бота: зчитує токени та налаштування з .env файлу.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Список ID адмінів, яким приходять сповіщення про нові заявки
ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

DB_PATH = "car_repair_bot.db"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не знайдено. Заповніть файл .env (див. .env.example)")
