import asyncio
from aiogram import Bot, Dispatcher
from app.config import settings
from app.services.bootstrap import init_db
from app.bot.handlers.start import router as start_router
from app.bot.handlers.orders import router as orders_router
from app.bot.handlers.prices import router as prices_router
from app.bot.handlers.calendar import router as calendar_router
from app.bot.handlers.documents import router as documents_router
from app.bot.handlers.settings import router as settings_router

async def main():
    await init_db()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(orders_router)
    dp.include_router(prices_router)
    dp.include_router(calendar_router)
    dp.include_router(documents_router)
    dp.include_router(settings_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
