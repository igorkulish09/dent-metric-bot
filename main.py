import asyncio
import inspect
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

import config
import database as db
from access import AccessMiddleware
from reminders import run_reminder_loop

from handlers import start, calculator, journal, order_detail, appointments, admin

logger = logging.getLogger(__name__)

# Функції, без яких бот впаде десь посеред роботи (а не одразу, зрозуміло
# де). Найчастіша причина — оновили не всі файли проєкту одночасно.
_REQUIRED_DB_FUNCTIONS = (
    "create_order", "update_order_field", "get_order", "list_orders",
    "delete_order", "add_dent", "list_dents", "delete_dent", "order_total",
    "set_appointment", "clear_appointment", "list_orders_by_date",
    "list_scheduled_orders_for_reminders", "mark_reminder_sent",
)


def self_check() -> bool:
    """Перевіряє, що всі файли проєкту синхронізовані між собою. Якщо
    щось не так — пише зрозумілою мовою що саме не так, замість того щоб
    впасти пізніше з незрозумілим трейсбеком."""
    problems = []

    missing_db = [fn for fn in _REQUIRED_DB_FUNCTIONS if not hasattr(db, fn)]
    if missing_db:
        problems.append(
            "У database.py бракує функцій: " + ", ".join(missing_db) + ". "
            "Онови database.py до останньої версії."
        )

    try:
        import keyboards
        if not hasattr(keyboards, "calendar_kb"):
            problems.append("У keyboards.py немає calendar_kb — онови keyboards.py.")
    except Exception as e:
        problems.append(f"Не вдалось імпортувати keyboards.py: {e}")

    try:
        import states
        if not hasattr(states, "ScheduleForm"):
            problems.append("У states.py немає ScheduleForm — онови states.py.")
        if not (hasattr(states, "DentForm") and hasattr(states.DentForm, "width")
                and hasattr(states.DentForm, "length")):
            problems.append(
                "У states.py немає кроків розміру вм'ятини (width/length) — онови states.py."
            )
    except Exception as e:
        problems.append(f"Не вдалось імпортувати states.py: {e}")

    try:
        sig_params = inspect.signature(db.add_dent).parameters
        if "width_cm" not in sig_params or "length_cm" not in sig_params:
            problems.append(
                "database.py: add_dent() не приймає width_cm/length_cm — "
                "запит розміру вм'ятини не буде зберігатись. Онови database.py."
            )
    except Exception as e:
        problems.append(f"Не вдалось перевірити сигнатуру add_dent: {e}")

    try:
        import handlers.calculator as calc_module
        if not hasattr(calc_module, "dent_width_entered") or not hasattr(calc_module, "dent_length_entered"):
            problems.append(
                "У handlers/calculator.py немає кроків запиту ширини/довжини — "
                "онови handlers/calculator.py."
            )
    except Exception as e:
        problems.append(f"Не вдалось імпортувати handlers/calculator.py: {e}")

    try:
        import handlers.appointments as appt_module
        if not hasattr(appt_module, "order_schedule_start"):
            problems.append(
                "У handlers/appointments.py немає календаря запису — "
                "онови handlers/appointments.py."
            )
    except Exception as e:
        problems.append(
            f"Не вдалось імпортувати handlers/appointments.py: {e} "
            "(файл календаря запису відсутній або застарілий)"
        )

    try:
        from pdf_generator import FONT_NAME
        if FONT_NAME == "Helvetica":
            problems.append(
                "Шрифт для кирилиці не завантажився (використовується Helvetica) — "
                "акти будуть із квадратиками замість тексту. Перевір, що файл "
                "font_data.py на місці поруч з pdf_generator.py."
            )
    except Exception as e:
        problems.append(f"Не вдалось імпортувати pdf_generator.py: {e}")

    if problems:
        print("\n" + "=" * 60)
        print("⚠️  ПЕРЕВІРКА ПРОЄКТУ ЗНАЙШЛА ПРОБЛЕМИ:")
        for p in problems:
            print(f"  • {p}")
        print("Найнадійніше — розпакувати останній архів проєкту повністю")
        print("поверх поточної папки, а не копіювати файли поштучно.")
        print("=" * 60 + "\n")
        return False

    return True


async def main():
    logging.basicConfig(level=logging.INFO)

    if not config.BOT_TOKEN:
        raise RuntimeError(
            "Не знайдено BOT_TOKEN. Створи файл .env на основі .env.example "
            "і встав туди токен від @BotFather."
        )

    if not self_check():
        sys.exit(1)

    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(calculator.router)
    dp.include_router(journal.router)
    dp.include_router(order_detail.router)
    dp.include_router(appointments.router)

    @dp.errors()
    async def global_error_handler(event: ErrorEvent):
        """Ловимо будь-які необроблені винятки в хендлерах, щоб дрібні
        збої (наприклад, застарілий callback через затримку мережі) не
        валили процес обробки й не засмічували консоль страшним трейсбеком."""
        exc = event.exception
        harmless_messages = ("query is too old", "message is not modified")
        if isinstance(exc, TelegramBadRequest) and any(m in str(exc).lower() for m in harmless_messages):
            logger.warning("Незначна помилка Telegram API (проігноровано): %s", exc)
        else:
            logger.exception("Необроблена помилка під час обробки апдейту", exc_info=exc)
        return True  # не даємо винятку піти далі

    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(run_reminder_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
