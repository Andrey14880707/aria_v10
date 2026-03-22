"""
München Barber — Telegram бот для записи на стрижку.
Запуск: python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import admin, booking, my_bookings, start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    db.init_db()
    log.info("DB initialised at %s", db.DB_PATH)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Order matters: admin first (has filter), then booking/my_bookings/start
    dp.include_router(admin.router)
    dp.include_router(booking.router)
    dp.include_router(my_bookings.router)
    dp.include_router(start.router)

    log.info("Starting München Barber bot…")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
