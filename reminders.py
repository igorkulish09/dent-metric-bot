import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

import database as db

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


def _order_title(o: dict) -> str:
    return o["car_make"] or o["client_name"] or f"Замовлення #{o['id']}"


async def run_reminder_loop(bot: Bot):
    """Раз на хвилину перевіряє записи й шле нагадування майстру:
    за добу до запису і за годину до запису."""
    while True:
        try:
            await _check_once(bot)
        except Exception:
            logger.exception("Помилка в циклі нагадувань")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _check_once(bot: Bot):
    now = datetime.now()
    orders = await db.list_scheduled_orders_for_reminders()

    for o in orders:
        try:
            appt = datetime.strptime(
                f"{o['appointment_date']} {o['appointment_time']}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            continue

        if appt < now:
            continue  # запис уже минув

        remaining = appt - now
        title = _order_title(o)
        date_fmt = appt.strftime("%d.%m.%Y")
        time_fmt = appt.strftime("%H:%M")

        if not o["reminder_day_sent"] and remaining <= timedelta(hours=24):
            text = (
                f"⏰ Нагадування: завтра запис на ремонт\n\n"
                f"🚗 {title}\n📅 {date_fmt} о {time_fmt}"
            )
            await _send(bot, o["master_id"], text)
            await db.mark_reminder_sent(o["id"], "reminder_day_sent")

        if not o["reminder_hour_sent"] and remaining <= timedelta(hours=1):
            text = (
                f"⏰ Нагадування: за годину запис на ремонт\n\n"
                f"🚗 {title}\n📅 {date_fmt} о {time_fmt}"
            )
            await _send(bot, o["master_id"], text)
            await db.mark_reminder_sent(o["id"], "reminder_hour_sent")


async def _send(bot: Bot, chat_id: int, text: str):
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("Не вдалось надіслати нагадування user_id=%s", chat_id)
