from aiogram import Dispatcher
from aiogram.types import Message

from keyboards import main_menu

INFO_TEXT = (
    "💈 <b>München Barber</b>\n\n"
    "Профессиональная мужская стрижка в Мюнхене.\n\n"
    "📍 Адрес: <i>укажите адрес</i>\n"
    "🕐 Пн–Сб: 10:00 – 20:00\n"
    "📞 Телефон: <i>укажите телефон</i>\n"
    "📸 Instagram: @MunchenBarber"
)


async def cmd_start(msg: Message) -> None:
    name = msg.from_user.first_name or "Друг"
    await msg.answer(
        f"✂️ Привет, <b>{name}</b>! Добро пожаловать в <b>München Barber</b>.\n\n"
        "Здесь ты можешь быстро записаться на стрижку или бороду.\n"
        "Выбери действие в меню ниже 👇",
        reply_markup=main_menu(),
    )


async def cmd_info(msg: Message) -> None:
    await msg.answer(INFO_TEXT)


def register(dp: Dispatcher) -> None:
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_message_handler(cmd_info,  text="ℹ️ О нас")
