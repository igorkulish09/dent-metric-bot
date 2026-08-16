from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import config
import database as db


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not config.RESTRICT_ACCESS:
            return await handler(event, data)

        user = data.get("event_from_user")
        user_id = user.id if user else None
        allowed = user_id is not None and (
            user_id in config.ADMIN_USER_IDS or await db.is_master(user_id)
        )

        if allowed:
            return await handler(event, data)

        text = (
            "⛔ <b>У вас немає доступу до цього бота.</b>\n\n"
            "Зверніться до адміністратора та передайте йому свій Telegram ID.\n"
            "Його можна дізнатися через @userinfobot."
        )
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Немає доступу", show_alert=True)
        return None
