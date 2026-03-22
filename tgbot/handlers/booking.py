"""Booking flow: service → master → date → time → phone → confirm (aiogram 2.x)."""

import logging
from datetime import date

from aiogram import Dispatcher, Bot
from aiogram.dispatcher import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

import config
import db
import keyboards as kb
from keyboards import fmt_date
from states import BookingFSM

log = logging.getLogger(__name__)


def _summary(data: dict) -> str:
    return (
        f"📋 <b>Ваша запись:</b>\n\n"
        f"✂️ Услуга:  {data['svc_name']} ({data['duration']} мин)\n"
        f"💰 Цена:    {data['price']}€\n"
        f"💈 Мастер:  {data['master_name']}\n"
        f"📅 Дата:    {fmt_date(data['date'])}\n"
        f"🕐 Время:   {data['time']}\n"
        f"📱 Телефон: {data.get('phone') or 'не указан'}"
    )


# ── Start ──────────────────────────────────────────────────────────────────────

async def start_booking(msg: Message, state: FSMContext) -> None:
    await state.finish()
    await BookingFSM.choose_service.set()
    await msg.answer("🗓 Начинаем запись!\n\nВыбери услугу:", reply_markup=kb.services_kb())


# ── Service ────────────────────────────────────────────────────────────────────

async def choose_service(cb: CallbackQuery, state: FSMContext) -> None:
    sid = int(cb.data.split(":")[1])
    svc = db.get_service(sid)
    if not svc:
        await cb.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(service_id=sid, svc_name=svc["name"],
                            duration=svc["duration"], price=svc["price"])
    await BookingFSM.choose_master.set()
    await cb.message.edit_text(
        f"Выбрано: <b>{svc['name']}</b> ({svc['duration']} мин, {svc['price']}€)\n\nВыбери мастера:",
        reply_markup=kb.masters_kb(sid),
    )
    await cb.answer()


# ── Master ─────────────────────────────────────────────────────────────────────

async def choose_master(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    mid, sid = int(parts[1]), int(parts[2])
    master_name = "Любой мастер" if mid == 0 else db.get_master(mid)["name"]
    data = await state.get_data()
    await state.update_data(master_id=mid, master_name=master_name)
    await BookingFSM.choose_date.set()
    await cb.message.edit_text(
        f"Мастер: <b>{master_name}</b>\n\nВыбери дату:",
        reply_markup=kb.dates_kb(sid, mid, data["duration"]),
    )
    await cb.answer()


# ── Date ───────────────────────────────────────────────────────────────────────

async def choose_date(cb: CallbackQuery, state: FSMContext) -> None:
    _, day_str, sid, mid = cb.data.split(":")
    sid, mid = int(sid), int(mid)
    data = await state.get_data()

    if mid == 0:
        best_master, best_count = None, 0
        for m in db.get_masters():
            slots = db.get_available_slots(m["id"], date.fromisoformat(day_str), data["duration"])
            if len(slots) > best_count:
                best_count, best_master = len(slots), m
        if not best_master:
            await cb.answer("Нет свободных мастеров", show_alert=True)
            return
        mid = best_master["id"]
        await state.update_data(master_id=mid, master_name=best_master["name"])

    slots = db.get_available_slots(mid, date.fromisoformat(day_str), data["duration"])
    if not slots:
        await cb.answer("Нет свободных слотов", show_alert=True)
        return

    await state.update_data(date=day_str)
    await BookingFSM.choose_time.set()
    await cb.message.edit_text(
        f"📅 Дата: <b>{fmt_date(day_str)}</b>\n\nВыбери время:",
        reply_markup=kb.times_kb(slots, day_str, sid, mid),
    )
    await cb.answer()


# ── Time ───────────────────────────────────────────────────────────────────────

async def choose_time(cb: CallbackQuery, state: FSMContext) -> None:
    parts   = cb.data.split(":")
    time_str = f"{parts[1]}:{parts[2]}"
    day_str  = parts[3]
    mid      = int(parts[5])

    data = await state.get_data()
    if mid != data.get("master_id"):
        m = db.get_master(mid)
        await state.update_data(master_id=mid, master_name=m["name"] if m else "—")

    await state.update_data(time=time_str)
    await BookingFSM.enter_phone.set()
    await cb.message.edit_text(f"🕐 Время: <b>{time_str}</b>\n\nПоделись номером (необязательно):")
    await cb.message.answer("👇 Нажми кнопку или введи вручную:", reply_markup=kb.phone_kb())
    await cb.answer()


# ── Phone ──────────────────────────────────────────────────────────────────────

async def phone_contact(msg: Message, state: FSMContext) -> None:
    await state.update_data(phone=msg.contact.phone_number)
    await _show_confirm(msg, state)


async def phone_skip(msg: Message, state: FSMContext) -> None:
    await state.update_data(phone=None)
    await _show_confirm(msg, state)


async def phone_text(msg: Message, state: FSMContext) -> None:
    await state.update_data(phone=msg.text.strip())
    await _show_confirm(msg, state)


async def _show_confirm(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await BookingFSM.confirm.set()
    await msg.answer(
        _summary(data) + "\n\n<b>Всё верно?</b>",
        reply_markup=kb.confirm_kb(data["service_id"], data["master_id"], data["date"], data["time"]),
    )
    await msg.answer("👆", reply_markup=ReplyKeyboardRemove())


# ── Confirm ────────────────────────────────────────────────────────────────────

async def confirm_booking(cb: CallbackQuery, state: FSMContext) -> None:
    parts    = cb.data.split(":")
    sid, mid = int(parts[1]), int(parts[2])
    day_str  = parts[3]
    time_str = f"{parts[4]}:{parts[5]}"

    data = await state.get_data()
    user = cb.from_user

    slots = db.get_available_slots(mid, date.fromisoformat(day_str), data["duration"])
    if time_str not in slots:
        await cb.answer("😔 Это время уже занято. Выбери другое.", show_alert=True)
        await state.finish()
        return

    bid = db.create_booking(
        user_id=user.id, user_name=user.username or user.full_name,
        phone=data.get("phone"), master_id=mid, service_id=sid,
        day=day_str, time=time_str,
    )
    await state.finish()

    await cb.message.edit_text(
        f"🎉 <b>Запись подтверждена!</b>\n\n"
        + _summary(data)
        + f"\n\n🔖 Номер записи: #{bid}\n\nЖдём тебя! Если нужно отменить — «📋 Мои записи».",
        reply_markup=None,
    )
    await cb.message.answer("Главное меню:", reply_markup=kb.main_menu())
    await cb.answer("✅ Запись создана!")

    # Notify admins
    from aiogram import Bot as _Bot
    bot = _Bot.get_current()
    admin_text = (
        f"🔔 <b>Новая запись #{bid}</b>\n\n"
        f"👤 @{user.username or '—'} ({user.full_name})\n"
        f"📱 {data.get('phone') or '—'}\n"
        f"✂️ {data['svc_name']} ({data['duration']} мин, {data['price']}€)\n"
        f"💈 {data['master_name']}\n"
        f"📅 {fmt_date(day_str)}  🕐 {time_str}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=kb.admin_booking_kb(bid))
        except Exception:
            pass


# ── Back navigation ────────────────────────────────────────────────────────────

async def go_back(cb: CallbackQuery, state: FSMContext) -> None:
    target = cb.data.split(":")[1]
    data   = await state.get_data()

    if target == "service":
        await BookingFSM.choose_service.set()
        await cb.message.edit_text("Выбери услугу:", reply_markup=kb.services_kb())
    elif target == "master":
        await BookingFSM.choose_master.set()
        await cb.message.edit_text("Выбери мастера:", reply_markup=kb.masters_kb(data["service_id"]))
    elif target == "date":
        await BookingFSM.choose_date.set()
        await cb.message.edit_text(
            "Выбери дату:",
            reply_markup=kb.dates_kb(data["service_id"], data["master_id"], data["duration"]),
        )
    await cb.answer()


async def cancel_flow(cb: CallbackQuery, state: FSMContext) -> None:
    await state.finish()
    await cb.message.edit_text("❌ Запись отменена.")
    await cb.message.answer("Главное меню:", reply_markup=kb.main_menu())
    await cb.answer()


async def noop(cb: CallbackQuery) -> None:
    await cb.answer()


# ── Register ───────────────────────────────────────────────────────────────────

def register(dp: Dispatcher) -> None:
    dp.register_message_handler(start_booking, text="✂️ Записаться", state="*")

    dp.register_callback_query_handler(choose_service, lambda c: c.data.startswith("svc:"),    state=BookingFSM.choose_service)
    dp.register_callback_query_handler(choose_master,  lambda c: c.data.startswith("master:"), state=BookingFSM.choose_master)
    dp.register_callback_query_handler(choose_date,    lambda c: c.data.startswith("date:"),   state=BookingFSM.choose_date)
    dp.register_callback_query_handler(choose_time,    lambda c: c.data.startswith("time:"),   state=BookingFSM.choose_time)

    dp.register_message_handler(phone_contact, content_types=["contact"], state=BookingFSM.enter_phone)
    dp.register_message_handler(phone_skip,    text="⏭ Пропустить",       state=BookingFSM.enter_phone)
    dp.register_message_handler(phone_text,    content_types=["text"],     state=BookingFSM.enter_phone)

    dp.register_callback_query_handler(confirm_booking, lambda c: c.data.startswith("confirm:"), state=BookingFSM.confirm)

    dp.register_callback_query_handler(go_back,      lambda c: c.data.startswith("back:") and c.data != "back:my_bookings", state="*")
    dp.register_callback_query_handler(cancel_flow,  lambda c: c.data == "cancel", state="*")
    dp.register_callback_query_handler(noop,         lambda c: c.data == "noop")
