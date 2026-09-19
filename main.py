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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import config
import database as db
from access import AccessMiddleware
from reminders import run_reminder_loop
from handlers import start, calculator, journal, order_detail, appointments, admin

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dent-metric-local-webhook-secret")
reminder_task: asyncio.Task | None = None

_REQUIRED_DB_FUNCTIONS = (
    "create_order", "update_order_field", "get_order", "list_orders",
    "delete_order", "add_dent", "list_dents", "delete_dent", "order_total",
    "set_appointment", "clear_appointment", "list_orders_by_date",
    "list_scheduled_orders_for_reminders", "mark_reminder_sent",
)


def self_check() -> bool:
    problems = []

    missing_db = [fn for fn in _REQUIRED_DB_FUNCTIONS if not hasattr(db, fn)]
    if missing_db:
        problems.append("У database.py бракує функцій: " + ", ".join(missing_db))

    try:
        import keyboards
        if not hasattr(keyboards, "calendar_kb"):
            problems.append("У keyboards.py немає calendar_kb")
    except Exception as exc:
        problems.append(f"Не вдалось імпортувати keyboards.py: {exc}")

    try:
        import states
        if not hasattr(states, "ScheduleForm"):
            problems.append("У states.py немає ScheduleForm")
        if not (hasattr(states, "DentForm") and hasattr(states.DentForm, "width") and hasattr(states.DentForm, "length")):
            problems.append("У states.py немає DentForm.width/length")
    except Exception as exc:
        problems.append(f"Не вдалось імпортувати states.py: {exc}")

    try:
        params = inspect.signature(db.add_dent).parameters
        if "width_cm" not in params or "length_cm" not in params:
            problems.append("database.add_dent() не приймає width_cm/length_cm")
    except Exception as exc:
        problems.append(f"Не вдалось перевірити add_dent(): {exc}")

    try:
        import handlers.calculator as calc_module
        if not hasattr(calc_module, "dent_width_entered") or not hasattr(calc_module, "dent_length_entered"):
            problems.append("У handlers/calculator.py немає dent_width_entered/dent_length_entered")
    except Exception as exc:
        problems.append(f"Не вдалось імпортувати handlers/calculator.py: {exc}")

    try:
        import handlers.appointments as appt_module
        if not hasattr(appt_module, "order_schedule_start"):
            problems.append("У handlers/appointments.py немає order_schedule_start")
    except Exception as exc:
        problems.append(f"Не вдалось імпортувати handlers/appointments.py: {exc}")

    try:
        from pdf_generator import FONT_NAME
        if FONT_NAME == "Helvetica":
            problems.append("PDF: не завантажився кириличний шрифт (Helvetica)")
    except Exception as exc:
        problems.append(f"Не вдалось імпортувати pdf_generator.py: {exc}")

    if problems:
        print("\n" + "=" * 60)
        print("⚠️ ПЕРЕВІРКА ПРОЄКТУ ЗНАЙШЛА ПРОБЛЕМИ:")
        for problem in problems:
            print(f"  • {problem}")
        print("=" * 60 + "\n")
        return False
    return True


async def root_handler(request: web.Request) -> web.Response:
    return web.Response(text="Dent Metric Bot is running.", content_type="text/plain")


async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "dent-metric-bot"})


async def on_startup(bot: Bot) -> None:
    global reminder_task

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if not render_url:
        raise RuntimeError("RENDER_EXTERNAL_URL не знайдено. Запуск очікує Render.")

    webhook_url = f"{render_url.rstrip('/')}{WEBHOOK_PATH}"
    logger.info("Встановлюємо Telegram webhook: %s", webhook_url)

    await bot.set_webhook(
        url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )
    logger.info("Telegram webhook успішно встановлено.")

    if reminder_task is None or reminder_task.done():
        reminder_task = asyncio.create_task(run_reminder_loop(bot))
        logger.info("Reminder loop запущено.")


async def on_shutdown(bot: Bot) -> None:
    global reminder_task
    logger.info("Завершення роботи Dent Metric Bot...")

    if reminder_task is not None:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Помилка під час зупинки reminder loop")
        reminder_task = None

    try:
        await bot.delete_webhook()
        logger.info("Telegram webhook видалено.")
    except Exception:
        logger.exception("Не вдалося видалити Telegram webhook")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger.info("Запуск Dent Metric Bot...")

    if not config.BOT_TOKEN:
        raise RuntimeError(
            "Не знайдено BOT_TOKEN. Додай BOT_TOKEN у Render Environment або створи .env локально."
        )

    if not self_check():
        sys.exit(1)

    logger.info("Ініціалізація бази даних...")
    await db.init_db()
    logger.info("База даних готова.")

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
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
        exc = event.exception
        harmless = ("query is too old", "message is not modified")
        if isinstance(exc, TelegramBadRequest) and any(x in str(exc).lower() for x in harmless):
            logger.warning("Незначна помилка Telegram API (проігноровано): %s", exc)
        else:
            logger.exception("Необроблена помилка під час обробки update", exc_info=exc)
        return True

    app = web.Application()
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_check)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)

    # Connect aiogram lifecycle to aiohttp. No web.run_app() here:
    # main() already owns the asyncio event loop.
    setup_application(app, dp, bot=bot)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    port = int(os.getenv("PORT", "10000"))
    logger.info("Підготовка HTTP сервера на 0.0.0.0:%s", port)

    # AppRunner/TCPSite reuse the existing asyncio loop.
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    logger.info("HTTP сервер успішно запущено на 0.0.0.0:%s", port)
    logger.info("Dent Metric Bot готовий до роботи.")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Основний asyncio task скасовано.")
    finally:
        logger.info("Зупиняємо HTTP сервер...")
        await runner.cleanup()
        logger.info("HTTP сервер зупинено.")
        try:
            await bot.session.close()
            logger.info("Bot session закрито.")
        except Exception:
            logger.exception("Не вдалося закрити Bot session")


if __name__ == "__main__":
    asyncio.run(main())