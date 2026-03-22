"""Booking flow: service → master → date → time → phone → confirm."""

import logging
from datetime import date

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

import config
import db
import keyboards as kb
from keyboards import fmt_date
from states import BookingFSM

log = logging.getLogger(__name__)
router = Router()


def _booking_summary(data: dict) -> str:
    return (
        f"📋 <b>Ваша запись:</b>\n\n"
        f"✂️ Услуга:  {data['svc_name']} ({data['duration']} мин)\n"
        f"💰 Цена:    {data['price']}€\n"
        f"💈 Мастер:  {data['master_name']}\n"
        f"📅 Дата:    {fmt_date(data['date'])}\n"
        f"🕐 Время:   {data['time']}\n"
        f"📱 Телефон: {data.get('phone') or 'не указан'}"
    )


# ── Entry: "Записаться" button ─────────────────────────────────────────────────

@router.message(F.text == "✂️ Записаться")
async def start_booking(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BookingFSM.choose_service)
    await msg.answer(
        "🗓 Начинаем запись!\n\nВыбери услугу:",
        reply_markup=kb.services_kb(),
        parse_mode="HTML",
    )


# ── Service chosen ─────────────────────────────────────────────────────────────

@router.callback_query(BookingFSM.choose_service, F.data.startswith("svc:"))
async def choose_service(cb: CallbackQuery, state: FSMContext) -> None:
    sid = int(cb.data.split(":")[1])
    svc = db.get_service(sid)
    if not svc:
        await cb.answer("Услуга не найдена", show_alert=True)
        return

    await state.update_data(
        service_id=sid,
        svc_name=svc["name"],
        duration=svc["duration"],
        price=svc["price"],
    )
    await state.set_state(BookingFSM.choose_master)
    await cb.message.edit_text(
        f"Выбрано: <b>{svc['name']}</b> ({svc['duration']} мин, {svc['price']}€)\n\n"
        "Выбери мастера:",
        reply_markup=kb.masters_kb(sid),
        parse_mode="HTML",
    )
    await cb.answer()


# ── Master chosen ──────────────────────────────────────────────────────────────

@router.callback_query(BookingFSM.choose_master, F.data.startswith("master:"))
async def choose_master(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    mid, sid = int(parts[1]), int(parts[2])

    if mid == 0:
        master_name = "Любой мастер"
    else:
        m = db.get_master(mid)
        if not m:
            await cb.answer("Мастер не найден", show_alert=True)
            return
        master_name = m["name"]

    data = await state.get_data()
    await state.update_data(master_id=mid, master_name=master_name)
    await state.set_state(BookingFSM.choose_date)

    dates_markup = kb.dates_kb(sid, mid, data["duration"])
    await cb.message.edit_text(
        f"Мастер: <b>{master_name}</b>\n\nВыбери дату:",
        reply_markup=dates_markup,
        parse_mode="HTML",
    )
    await cb.answer()


# ── Date chosen ────────────────────────────────────────────────────────────────

@router.callback_query(BookingFSM.choose_date, F.data.startswith("date:"))
async def choose_date(cb: CallbackQuery, state: FSMContext) -> None:
    _, day_str, sid, mid = cb.data.split(":")
    sid, mid = int(sid), int(mid)
    data = await state.get_data()

    # If "any master" — pick master with most free slots on that day
    if mid == 0:
        best_master = None
        best_count = 0
        for m in db.get_masters():
            slots = db.get_available_slots(m["id"], date.fromisoformat(day_str), data["duration"])
            if len(slots) > best_count:
                best_count = len(slots)
                best_master = m
        if not best_master:
            await cb.answer("Нет свободных мастеров в этот день", show_alert=True)
            return
        mid = best_master["id"]
        await state.update_data(master_id=mid, master_name=best_master["name"])

    slots = db.get_available_slots(mid, date.fromisoformat(day_str), data["duration"])
    if not slots:
        await cb.answer("Нет свободных слотов в этот день", show_alert=True)
        return

    await state.update_data(date=day_str)
    await state.set_state(BookingFSM.choose_time)
    await cb.message.edit_text(
        f"📅 Дата: <b>{fmt_date(day_str)}</b>\n\nВыбери время:",
        reply_markup=kb.times_kb(slots, day_str, sid, mid),
        parse_mode="HTML",
    )
    await cb.answer()


# ── Time chosen ────────────────────────────────────────────────────────────────

@router.callback_query(BookingFSM.choose_time, F.data.startswith("time:"))
async def choose_time(cb: CallbackQuery, state: FSMContext) -> None:
    parts = cb.data.split(":")
    # time:HH:MM:day_str:sid:mid
    time_str = f"{parts[1]}:{parts[2]}"
    day_str   = parts[3]
    mid       = int(parts[5])

    data = await state.get_data()
    if mid != data.get("master_id"):
        await state.update_data(master_id=mid)
        m = db.get_master(mid)
        if m:
            await state.update_data(master_name=m["name"])

    await state.update_data(time=time_str)
    await state.set_state(BookingFSM.enter_phone)
    await cb.message.edit_text(
        f"🕐 Время: <b>{time_str}</b>\n\n"
        "Поделись номером телефона (необязательно) — мастер сможет связаться с тобой при необходимости.",
        parse_mode="HTML",
    )
    await cb.message.answer(
        "👇 Нажми кнопку или введи номер вручную:",
        reply_markup=kb.phone_kb(),
    )
    await cb.answer()


# ── Phone ──────────────────────────────────────────────────────────────────────

@router.message(BookingFSM.enter_phone, F.contact)
async def phone_contact(msg: Message, state: FSMContext) -> None:
    phone = msg.contact.phone_number
    await state.update_data(phone=phone)
    await _show_confirm(msg, state)


@router.message(BookingFSM.enter_phone, F.text == "⏭ Пропустить")
async def phone_skip(msg: Message, state: FSMContext) -> None:
    await state.update_data(phone=None)
    await _show_confirm(msg, state)


@router.message(BookingFSM.enter_phone, F.text)
async def phone_text(msg: Message, state: FSMContext) -> None:
    phone = msg.text.strip()
    await state.update_data(phone=phone)
    await _show_confirm(msg, state)


async def _show_confirm(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(BookingFSM.confirm)
    await msg.answer(
        _booking_summary(data) + "\n\n<b>Всё верно?</b>",
        reply_markup=kb.confirm_kb(
            data["service_id"], data["master_id"], data["date"], data["time"]
        ),
        parse_mode="HTML",
    )
    # Remove phone keyboard
    await msg.answer("👆", reply_markup=ReplyKeyboardRemove())


# ── Confirm ────────────────────────────────────────────────────────────────────

@router.callback_query(BookingFSM.confirm, F.data.startswith("confirm:"))
async def confirm_booking(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    parts = cb.data.split(":")
    sid, mid, day_str, time_str = int(parts[1]), int(parts[2]), parts[3], f"{parts[4]}:{parts[5]}"

    data = await state.get_data()
    user = cb.from_user

    # Double-check slot is still free
    slots = db.get_available_slots(mid, date.fromisoformat(day_str), data["duration"])
    if time_str not in slots:
        await cb.answer("😔 Это время уже занято. Выбери другое.", show_alert=True)
        await state.clear()
        return

    bid = db.create_booking(
        user_id=user.id,
        user_name=user.username or user.full_name,
        phone=data.get("phone"),
        master_id=mid,
        service_id=sid,
        day=day_str,
        time=time_str,
    )

    await state.clear()

    await cb.message.edit_text(
        f"🎉 <b>Запись подтверждена!</b>\n\n"
        + _booking_summary(data)
        + f"\n\n🔖 Номер записи: #{bid}\n\n"
        "Ждём тебя! Если нужно отменить — нажми «📋 Мои записи».",
        reply_markup=None,
        parse_mode="HTML",
    )
    await cb.message.answer("Главное меню:", reply_markup=kb.main_menu())
    await cb.answer("✅ Запись создана!")

    # Notify admins
    admin_text = (
        f"🔔 <b>Новая запись #{bid}</b>\n\n"
        f"👤 Клиент: @{user.username or '—'} ({user.full_name})\n"
        f"📱 Телефон: {data.get('phone') or '—'}\n"
        f"✂️ Услуга: {data['svc_name']} ({data['duration']} мин)\n"
        f"💰 Цена: {data['price']}€\n"
        f"💈 Мастер: {data['master_name']}\n"
        f"📅 Дата: {fmt_date(day_str)}\n"
        f"🕐 Время: {time_str}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text,
                parse_mode="HTML",
                reply_markup=kb.admin_booking_kb(bid),
            )
        except Exception:
            pass


# ── Back navigation ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("back:"))
async def go_back(cb: CallbackQuery, state: FSMContext) -> None:
    target = cb.data.split(":")[1]
    data = await state.get_data()

    if target == "service":
        await state.set_state(BookingFSM.choose_service)
        await cb.message.edit_text("Выбери услугу:", reply_markup=kb.services_kb())

    elif target == "master":
        await state.set_state(BookingFSM.choose_master)
        await cb.message.edit_text(
            f"Выбери мастера:",
            reply_markup=kb.masters_kb(data["service_id"]),
        )

    elif target == "date":
        await state.set_state(BookingFSM.choose_date)
        await cb.message.edit_text(
            "Выбери дату:",
            reply_markup=kb.dates_kb(
                data["service_id"], data["master_id"], data["duration"]
            ),
        )

    await cb.answer()


# ── Cancel ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cancel_flow(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("❌ Запись отменена.")
    await cb.message.answer("Главное меню:", reply_markup=kb.main_menu())
    await cb.answer()


@router.callback_query(F.data == "noop")
async def noop(cb: CallbackQuery) -> None:
    await cb.answer()
