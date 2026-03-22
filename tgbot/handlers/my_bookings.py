"""View and cancel own bookings."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import db
import keyboards as kb
from keyboards import fmt_date

router = Router()


@router.message(F.text == "📋 Мои записи")
@router.message(Command("my"))
async def my_bookings(msg: Message) -> None:
    bookings = db.get_user_bookings(msg.from_user.id)
    if not bookings:
        await msg.answer(
            "📋 У тебя нет активных записей.\n\nНажми «✂️ Записаться», чтобы записаться!",
            reply_markup=kb.main_menu(),
        )
        return

    await msg.answer(
        f"📋 <b>Твои записи ({len(bookings)}):</b>\n\nВыбери запись для просмотра:",
        reply_markup=kb.my_bookings_kb(bookings),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("view_booking:"))
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
        f"📱 Телефон: {b['phone'] or '—'}\n"
        f"📌 Статус:  {'✅ активна' if b['status'] == 'active' else b['status']}"
    )
    await cb.message.edit_text(
        text,
        reply_markup=kb.booking_detail_kb(bid),
        parse_mode="HTML",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("cancel_booking:"))
async def cancel_booking(cb: CallbackQuery) -> None:
    bid = int(cb.data.split(":")[1])
    ok = db.cancel_booking(bid, cb.from_user.id)
    if ok:
        await cb.message.edit_text(
            f"❌ Запись #{bid} отменена.\n\nЕсли хочешь записаться снова — нажми «✂️ Записаться»."
        )
        await cb.answer("Запись отменена")
    else:
        await cb.answer("Не удалось отменить запись", show_alert=True)


@router.callback_query(F.data == "back:my_bookings")
async def back_to_my_bookings(cb: CallbackQuery) -> None:
    bookings = db.get_user_bookings(cb.from_user.id)
    if not bookings:
        await cb.message.edit_text("📋 Нет активных записей.")
        return
    await cb.message.edit_text(
        f"📋 <b>Твои записи ({len(bookings)}):</b>",
        reply_markup=kb.my_bookings_kb(bookings),
        parse_mode="HTML",
    )
    await cb.answer()
