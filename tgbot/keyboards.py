"""All keyboards for München Barber bot."""

from datetime import date, timedelta
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import db

RU_DAYS   = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RU_MONTHS = ["", "янв", "фев", "мар", "апр", "май", "июн",
             "июл", "авг", "сен", "окт", "ноя", "дек"]


# ── Main menu ──────────────────────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✂️ Записаться")],
            [KeyboardButton(text="📋 Мои записи"), KeyboardButton(text="ℹ️ О нас")],
        ],
        resize_keyboard=True,
    )


# ── Services ───────────────────────────────────────────────────────────────────

def services_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in db.get_services():
        builder.button(
            text=f"{s['name']} — {s['price']}€ ({s['duration']} мин)",
            callback_data=f"svc:{s['id']}",
        )
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


# ── Masters ────────────────────────────────────────────────────────────────────

def masters_kb(service_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎲 Любой мастер", callback_data=f"master:0:{service_id}")
    for m in db.get_masters():
        builder.button(
            text=f"💈 {m['name']}",
            callback_data=f"master:{m['id']}:{service_id}",
        )
    builder.button(text="⬅️ Назад", callback_data="back:service")
    builder.adjust(1)
    return builder.as_markup()


# ── Dates ──────────────────────────────────────────────────────────────────────

def dates_kb(service_id: int, master_id: int, duration: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    today = date.today()
    found = 0

    for delta in range(config.DAYS_AHEAD):
        day = today + timedelta(days=delta)
        # Check availability
        if master_id == 0:
            has_slot = db.any_master_has_slot(day, duration)
        else:
            has_slot = bool(db.get_available_slots(master_id, day, duration))

        if not has_slot:
            continue

        wd  = RU_DAYS[day.weekday()]
        mon = RU_MONTHS[day.month]
        label = f"{wd}, {day.day} {mon}"
        builder.button(
            text=label,
            callback_data=f"date:{day.isoformat()}:{service_id}:{master_id}",
        )
        found += 1

    if found == 0:
        builder.button(text="😔 Нет свободных дат", callback_data="noop")

    builder.button(text="⬅️ Назад", callback_data="back:master")
    builder.adjust(2)
    return builder.as_markup()


# ── Time slots ─────────────────────────────────────────────────────────────────

def times_kb(
    slots: list[str],
    day_str: str,
    service_id: int,
    master_id: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(
            text=slot,
            callback_data=f"time:{slot}:{day_str}:{service_id}:{master_id}",
        )
    builder.button(text="⬅️ Назад", callback_data="back:date")
    builder.adjust(3)
    return builder.as_markup()


# ── Phone ──────────────────────────────────────────────────────────────────────

def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="⏭ Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ── Confirm booking ────────────────────────────────────────────────────────────

def confirm_kb(service_id: int, master_id: int, day: str, time: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"confirm:{service_id}:{master_id}:{day}:{time}")
    builder.button(text="❌ Отмена",      callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


# ── My bookings ────────────────────────────────────────────────────────────────

def my_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in bookings:
        day = date.fromisoformat(b["date"])
        wd  = RU_DAYS[day.weekday()]
        mon = RU_MONTHS[day.month]
        builder.button(
            text=f"{wd} {day.day} {mon} {b['time']} — {b['svc_name']}",
            callback_data=f"view_booking:{b['id']}",
        )
    builder.adjust(1)
    return builder.as_markup()


def booking_detail_kb(bid: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить запись", callback_data=f"cancel_booking:{bid}")
    builder.button(text="⬅️ Назад",           callback_data="back:my_bookings")
    builder.adjust(1)
    return builder.as_markup()


# ── Admin ──────────────────────────────────────────────────────────────────────

def admin_booking_kb(bid: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнено",  callback_data=f"admin_done:{bid}")
    builder.button(text="❌ Отменить",   callback_data=f"admin_cancel:{bid}")
    builder.adjust(2)
    return builder.as_markup()


# ── Helpers ────────────────────────────────────────────────────────────────────

def fmt_date(day_str: str) -> str:
    day = date.fromisoformat(day_str)
    wd  = RU_DAYS[day.weekday()]
    mon = RU_MONTHS[day.month]
    return f"{wd}, {day.day} {mon}"
