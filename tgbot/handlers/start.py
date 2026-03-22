from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from keyboards import main_menu

router = Router()

INFO_TEXT = (
    "💈 <b>München Barber</b>\n\n"
    "Профессиональная мужская стрижка в Мюнхене.\n\n"
    "📍 Адрес: <i>укажите адрес</i>\n"
    "🕐 Пн–Сб: 10:00 – 20:00\n"
    "📞 Телефон: <i>укажите телефон</i>\n"
    "📸 Instagram: @MunchenBarber"
)


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    name = msg.from_user.first_name or "Друг"
    await msg.answer(
        f"✂️ Привет, <b>{name}</b>! Добро пожаловать в <b>München Barber</b>.\n\n"
        "Здесь ты можешь быстро записаться на стрижку или бороду.\n"
        "Выбери действие в меню ниже 👇",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )


@router.message(lambda m: m.text == "ℹ️ О нас")
async def cmd_info(msg: Message) -> None:
    await msg.answer(INFO_TEXT, parse_mode="HTML")
