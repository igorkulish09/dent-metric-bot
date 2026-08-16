import os
from dotenv import load_dotenv

# encoding="utf-8-sig" сам прибирає BOM-мітку (невидимий символ на початку
# файлу), яку іноді додають текстові редактори на macOS/Windows при
# збереженні .env — без цього python-dotenv не може розпарсити перший рядок.
load_dotenv(encoding="utf-8-sig")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

_raw_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = {
    int(x.strip()) for x in _raw_ids.split(",") if x.strip().isdigit()
}
# Якщо список порожній — доступ мають усі (зручно для першого запуску,
# але після тесту обов'язково впиши свій ID у .env)
# Адміністратори можуть додавати/видаляти майстрів прямо в Telegram.
# Якщо ADMIN_USER_IDS не заданий, старий ALLOWED_USER_IDS використовується
# як список адміністраторів — це зберігає сумісність із попередньою версією.
_raw_admin_ids = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = {
    int(x.strip()) for x in _raw_admin_ids.split(",") if x.strip().isdigit()
} or ALLOWED_USER_IDS

# Доступ обмежений, якщо заданий хоча б один адміністратор.
RESTRICT_ACCESS = len(ADMIN_USER_IDS) > 0

COMPANY_NAME = os.getenv("COMPANY_NAME", "ФОП ______________")
COMPANY_TAX_ID = os.getenv("COMPANY_TAX_ID", "")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "")
COMPANY_PHONE = os.getenv("COMPANY_PHONE", "")

DB_PATH = os.getenv("DB_PATH", "dentbot.sqlite3")
