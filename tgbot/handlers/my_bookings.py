from aiogram import Dispatcher
from aiogram.types import Message, CallbackQuery

import db
import keyboards as kb
from keyboards import fmt_date


async def my_bookings(msg: Message) -> None:
    bookings = db.get_user_bookings(msg.from_user.id)
    if not bookings:
        await msg.answer(
            "📋 У тебя нет активных записей.\n\nНажми «✂️ Записаться»!",
            reply_markup=kb.main_menu(),
        )
        return
    await msg.answer(
        f"📋 <b>Твои записи ({len(bookings)}):</b>\n\nВыбери запись:",
        reply_markup=kb.my_bookings_kb(bookings),
    )


async def view_booking(cb: CallbackQuery) -> None:
    bid = int(cb.data.split(":")[1])
    b = db.get_booking(bid)
    if not b or b["user_id"] != cb.from_user.id:
        await cb.answer("Запись не найдена", show_alert=True)
        return
    text = (
        f"📋 <b>Запись #{b['id']}</b>\n\n"
        f"✂️ Услуга:  {b['svc_name']} ({b['duration']} мин)\n"
        f"💰 Цена:    {b['price']}€\n"
        f"💈 Мастер:  {b['master_name']}\n"
        f"📅 Дата:    {fmt_date(b['date'])}\n"
        f"🕐 Время:   {b['time']}\n"
        f"📱 Телефон: {b['phone'] or '—'}"
    )
    await cb.message.edit_text(text, reply_markup=kb.booking_detail_kb(bid))
    await cb.answer()


async def cancel_booking(cb: CallbackQuery) -> None:
    bid = int(cb.data.split(":")[1])
    ok = db.cancel_booking(bid, cb.from_user.id)
    if ok:
        await cb.message.edit_text(f"❌ Запись #{bid} отменена.")
        await cb.answer("Запись отменена")
    else:
        await cb.answer("Не удалось отменить", show_alert=True)


async def back_my_bookings(cb: CallbackQuery) -> None:
    bookings = db.get_user_bookings(cb.from_user.id)
    if not bookings:
        await cb.message.edit_text("📋 Нет активных записей.")
    else:
        await cb.message.edit_text(
            f"📋 <b>Твои записи ({len(bookings)}):</b>",
            reply_markup=kb.my_bookings_kb(bookings),
        )
    await cb.answer()


def register(dp: Dispatcher) -> None:
    dp.register_message_handler(my_bookings,    text="📋 Мои записи")
    dp.register_message_handler(my_bookings,    commands=["my"])
    dp.register_callback_query_handler(view_booking,    lambda c: c.data.startswith("view_booking:"))
    dp.register_callback_query_handler(cancel_booking,  lambda c: c.data.startswith("cancel_booking:"))
    dp.register_callback_query_handler(back_my_bookings, lambda c: c.data == "back:my_bookings")
