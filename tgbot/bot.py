"""München Barber — Telegram бот для записи. Запуск: python bot.py"""

import logging
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import config
import db
from handlers import admin, booking, my_bookings, start

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")


def main() -> None:
    db.init_db()

    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    dp  = Dispatcher(bot, storage=MemoryStorage())

    admin.register(dp)
    booking.register(dp)
    my_bookings.register(dp)
    start.register(dp)

    logging.info("München Barber bot started")
    executor.start_polling(dp, skip_updates=True)


if __name__ == "__main__":
    main()
