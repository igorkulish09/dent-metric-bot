import asyncio
import inspect
import logging
import os
import sys

from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

import config
import database as db
from access import AccessMiddleware
from reminders import run_reminder_loop

from handlers import (
    start,
    calculator,
    journal,
    order_detail,
    appointments,
    admin,
)


logger = logging.getLogger(__name__)


# ============================================================
# Render / Webhook configuration
# ============================================================

WEBHOOK_PATH = "/webhook"

# Render automatically provides:
# RENDER_EXTERNAL_URL
# PORT
#
# WEBHOOK_SECRET should be added manually in Render Environment.
WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "dent-metric-local-webhook-secret",
)


# ============================================================
# Required database functions
# ============================================================

_REQUIRED_DB_FUNCTIONS = (
    "create_order",
    "update_order_field",
    "get_order",
    "list_orders",
    "delete_order",
    "add_dent",
    "list_dents",
    "delete_dent",
    "order_total",
    "set_appointment",
    "clear_appointment",
    "list_orders_by_date",
    "list_scheduled_orders_for_reminders",
    "mark_reminder_sent",
)


# Background task for reminders.
reminder_task = None


# ============================================================
# Project self-check
# ============================================================

def self_check() -> bool:
    """
    Перевіряє, що всі файли проєкту синхронізовані між собою.
    Якщо щось не так — пише зрозуміле повідомлення.
    """

    problems = []

    # --------------------------------------------------------
    # database.py
    # --------------------------------------------------------

    missing_db = [
        fn
        for fn in _REQUIRED_DB_FUNCTIONS
        if not hasattr(db, fn)
    ]

    if missing_db:
        problems.append(
            "У database.py бракує функцій: "
            + ", ".join(missing_db)
            + ". Онови database.py до останньої версії."
        )

    # --------------------------------------------------------
    # keyboards.py
    # --------------------------------------------------------

    try:
        import keyboards

        if not hasattr(keyboards, "calendar_kb"):
            problems.append(
                "У keyboards.py немає calendar_kb — "
                "онови keyboards.py."
            )

    except Exception as e:
        problems.append(
            f"Не вдалось імпортувати keyboards.py: {e}"
        )

    # --------------------------------------------------------
    # states.py
    # --------------------------------------------------------

    try:
        import states

        if not hasattr(states, "ScheduleForm"):
            problems.append(
                "У states.py немає ScheduleForm — "
                "онови states.py."
            )

        if not (
            hasattr(states, "DentForm")
            and hasattr(states.DentForm, "width")
            and hasattr(states.DentForm, "length")
        ):
            problems.append(
                "У states.py немає кроків розміру "
                "вм'ятини (width/length) — "
                "онови states.py."
            )

    except Exception as e:
        problems.append(
            f"Не вдалось імпортувати states.py: {e}"
        )

    # --------------------------------------------------------
    # database.add_dent()
    # --------------------------------------------------------

    try:
        sig_params = inspect.signature(
            db.add_dent
        ).parameters

        if (
            "width_cm" not in sig_params
            or "length_cm" not in sig_params
        ):
            problems.append(
                "database.py: add_dent() не приймає "
                "width_cm/length_cm — "
                "запит розміру вм'ятини не буде "
                "зберігатись. Онови database.py."
            )

    except Exception as e:
        problems.append(
            f"Не вдалось перевірити сигнатуру "
            f"add_dent: {e}"
        )

    # --------------------------------------------------------
    # handlers/calculator.py
    # --------------------------------------------------------

    try:
        import handlers.calculator as calc_module

        if not hasattr(
            calc_module,
            "dent_width_entered",
        ) or not hasattr(
            calc_module,
            "dent_length_entered",
        ):
            problems.append(
                "У handlers/calculator.py немає "
                "кроків запиту ширини/довжини — "
                "онови handlers/calculator.py."
            )

    except Exception as e:
        problems.append(
            "Не вдалось імпортувати "
            f"handlers/calculator.py: {e}"
        )

    # --------------------------------------------------------
    # handlers/appointments.py
    # --------------------------------------------------------

    try:
        import handlers.appointments as appt_module

        if not hasattr(
            appt_module,
            "order_schedule_start",
        ):
            problems.append(
                "У handlers/appointments.py немає "
                "календаря запису — "
                "онови handlers/appointments.py."
            )

    except Exception as e:
        problems.append(
            "Не вдалось імпортувати "
            f"handlers/appointments.py: {e} "
            "(файл календаря запису відсутній "
            "або застарілий)"
        )

    # --------------------------------------------------------
    # PDF / Cyrillic font
    # --------------------------------------------------------

    try:
        from pdf_generator import FONT_NAME

        if FONT_NAME == "Helvetica":
            problems.append(
                "Шрифт для кирилиці не завантажився "
                "(використовується Helvetica) — "
                "акти будуть із квадратиками замість "
                "тексту. Перевір, що файл "
                "font_data.py на місці поруч "
                "з pdf_generator.py."
            )

    except Exception as e:
        problems.append(
            f"Не вдалось імпортувати "
            f"pdf_generator.py: {e}"
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    if problems:
        print("\n" + "=" * 60)
        print(
            "⚠️  ПЕРЕВІРКА ПРОЄКТУ "
            "ЗНАЙШЛА ПРОБЛЕМИ:"
        )

        for problem in problems:
            print(f"  • {problem}")

        print(
            "Найнадійніше — розпакувати останній "
            "архів проєкту повністю поверх "
            "поточної папки, а не копіювати "
            "файли поштучно."
        )

        print("=" * 60 + "\n")

        return False

    return True


# ============================================================
# Web routes
# ============================================================

async def health_check(request: web.Request) -> web.Response:
    """
    Простий health-check для Render.
    """

    return web.json_response(
        {
            "status": "ok",
            "service": "dent-metric-bot",
        }
    )


async def root_handler(request: web.Request) -> web.Response:
    """
    Головна сторінка сервісу.
    """

    return web.Response(
        text="Dent Metric Bot is running.",
        content_type="text/plain",
    )


# ============================================================
# Telegram webhook startup
# ============================================================

async def on_startup(bot: Bot):
    """
    Встановлює Telegram webhook після запуску Render.
    """

    global reminder_task

    render_url = os.getenv("RENDER_EXTERNAL_URL")

    if not render_url:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL не знайдено. "
            "Цей застосунок очікує запуск на Render."
        )

    webhook_url = (
        f"{render_url.rstrip('/')}"
        f"{WEBHOOK_PATH}"
    )

    logger.info(
        "Встановлюємо Telegram webhook: %s",
        webhook_url,
    )

    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )

    logger.info(
        "Telegram webhook успішно встановлено."
    )

    # Запускаємо нагадування.
    reminder_task = asyncio.create_task(
        run_reminder_loop(bot)
    )

    logger.info(
        "Reminder loop запущено."
    )


# ============================================================
# Telegram webhook shutdown
# ============================================================

async def on_shutdown(bot: Bot):
    """
    Коректно завершує webhook та background task.
    """

    global reminder_task

    logger.info(
        "Завершення роботи Dent Metric Bot..."
    )

    # --------------------------------------------------------
    # Stop reminder loop
    # --------------------------------------------------------

    if reminder_task:
        reminder_task.cancel()

        try:
            await reminder_task
        except asyncio.CancelledError:
            pass

        reminder_task = None

        logger.info(
            "Reminder loop зупинено."
        )

    # --------------------------------------------------------
    # Remove Telegram webhook
    # --------------------------------------------------------

    try:
        await bot.delete_webhook()

        logger.info(
            "Telegram webhook видалено."
        )

    except Exception:
        logger.exception(
            "Не вдалося видалити Telegram webhook."
        )

    # --------------------------------------------------------
    # Close bot session
    # --------------------------------------------------------

    try:
        await bot.session.close()

        logger.info(
            "Bot session закрито."
        )

    except Exception:
        logger.exception(
            "Не вдалося закрити Bot session."
        )


# ============================================================
# Main
# ============================================================

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    logger.info(
        "Запуск Dent Metric Bot..."
    )

    # --------------------------------------------------------
    # BOT TOKEN
    # --------------------------------------------------------

    if not config.BOT_TOKEN:
        raise RuntimeError(
            "Не знайдено BOT_TOKEN. "
            "Додай BOT_TOKEN у Render Environment "
            "або створи .env локально."
        )

    # --------------------------------------------------------
    # Self check
    # --------------------------------------------------------

    if not self_check():
        sys.exit(1)

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    logger.info(
        "Ініціалізація бази даних..."
    )

    await db.init_db()

    logger.info(
        "База даних готова."
    )

    # --------------------------------------------------------
    # Bot
    # --------------------------------------------------------

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    # --------------------------------------------------------
    # Dispatcher
    # --------------------------------------------------------

    dp = Dispatcher()

    # --------------------------------------------------------
    # Access middleware
    # --------------------------------------------------------

    dp.message.middleware(
        AccessMiddleware()
    )

    dp.callback_query.middleware(
        AccessMiddleware()
    )

    # --------------------------------------------------------
    # Routers
    # --------------------------------------------------------

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(calculator.router)
    dp.include_router(journal.router)
    dp.include_router(order_detail.router)
    dp.include_router(appointments.router)

    # --------------------------------------------------------
    # Global error handler
    # --------------------------------------------------------

    @dp.errors()
    async def global_error_handler(
        event: ErrorEvent,
    ):
        """
        Ловимо необроблені помилки в хендлерах,
        щоб вони не валили весь процес.
        """

        exc = event.exception

        harmless_messages = (
            "query is too old",
            "message is not modified",
        )

        if (
            isinstance(
                exc,
                TelegramBadRequest,
            )
            and any(
                message in str(exc).lower()
                for message in harmless_messages
            )
        ):
            logger.warning(
                "Незначна помилка Telegram API "
                "(проігноровано): %s",
                exc,
            )

        else:
            logger.exception(
                "Необроблена помилка "
                "під час обробки апдейту",
                exc_info=exc,
            )

        return True

    # --------------------------------------------------------
    # Web application
    # --------------------------------------------------------

    app = web.Application()

    # Health check.
    app.router.add_get(
        "/",
        root_handler,
    )

    app.router.add_get(
        "/health",
        health_check,
    )

    # --------------------------------------------------------
    # Telegram webhook handler
    # --------------------------------------------------------

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )

    webhook_handler.register(
        app,
        path=WEBHOOK_PATH,
    )

    # --------------------------------------------------------
    # Connect aiogram lifecycle to aiohttp
    # --------------------------------------------------------

    setup_application(
        app,
        dp,
        bot=bot,
    )

    # --------------------------------------------------------
    # Startup / shutdown hooks
    # --------------------------------------------------------

    dp.startup.register(
        on_startup
    )

    dp.shutdown.register(
        on_shutdown
    )

    # --------------------------------------------------------
    # Render PORT
    # --------------------------------------------------------

    port = int(
        os.getenv(
            "PORT",
            "10000",
        )
    )

    logger.info(
        "Запускаємо HTTP сервер "
        "на 0.0.0.0:%s",
        port,
    )

    # --------------------------------------------------------
    # Start aiohttp
    # --------------------------------------------------------

    web.run_app(
        app,
        host="0.0.0.0",
        port=port,
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())