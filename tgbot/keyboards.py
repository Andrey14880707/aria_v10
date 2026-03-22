"""All keyboards for München Barber bot (aiogram 2.x)."""

from datetime import date, timedelta
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

import config
import db

RU_DAYS   = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RU_MONTHS = ["", "янв", "фев", "мар", "апр", "май", "июн",
             "июл", "авг", "сен", "окт", "ноя", "дек"]


def fmt_date(day_str: str) -> str:
    day = date.fromisoformat(day_str)
    return f"{RU_DAYS[day.weekday()]}, {day.day} {RU_MONTHS[day.month]}"


# ── Main menu ──────────────────────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("✂️ Записаться"))
    kb.row(KeyboardButton("📋 Мои записи"), KeyboardButton("ℹ️ О нас"))
    return kb


# ── Services ───────────────────────────────────────────────────────────────────

def services_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for s in db.get_services():
        kb.add(InlineKeyboardButton(
            text=f"{s['name']} — {s['price']}€ ({s['duration']} мин)",
            callback_data=f"svc:{s['id']}",
        ))
    kb.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return kb


# ── Masters ────────────────────────────────────────────────────────────────────

def masters_kb(service_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text="🎲 Любой мастер", callback_data=f"master:0:{service_id}"))
    for m in db.get_masters():
        kb.add(InlineKeyboardButton(text=f"💈 {m['name']}", callback_data=f"master:{m['id']}:{service_id}"))
    kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back:service"))
    return kb


# ── Dates ──────────────────────────────────────────────────────────────────────

def dates_kb(service_id: int, master_id: int, duration: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    today = date.today()
    found = 0

    for delta in range(config.DAYS_AHEAD):
        day = today + timedelta(days=delta)
        if master_id == 0:
            has_slot = db.any_master_has_slot(day, duration)
        else:
            has_slot = bool(db.get_available_slots(master_id, day, duration))

        if not has_slot:
            continue

        wd  = RU_DAYS[day.weekday()]
        mon = RU_MONTHS[day.month]
        kb.insert(InlineKeyboardButton(
            text=f"{wd}, {day.day} {mon}",
            callback_data=f"date:{day.isoformat()}:{service_id}:{master_id}",
        ))
        found += 1

    if found == 0:
        kb.add(InlineKeyboardButton(text="😔 Нет свободных дат", callback_data="noop"))

    kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back:master"))
    return kb


# ── Time slots ─────────────────────────────────────────────────────────────────

def times_kb(slots: list, day_str: str, service_id: int, master_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=3)
    for slot in slots:
        kb.insert(InlineKeyboardButton(
            text=slot,
            callback_data=f"time:{slot}:{day_str}:{service_id}:{master_id}",
        ))
    kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back:date"))
    return kb


# ── Phone ──────────────────────────────────────────────────────────────────────

def phone_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton(text="📱 Поделиться номером", request_contact=True))
    kb.add(KeyboardButton(text="⏭ Пропустить"))
    return kb


# ── Confirm ────────────────────────────────────────────────────────────────────

def confirm_kb(service_id: int, master_id: int, day: str, time: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{service_id}:{master_id}:{day}:{time}"),
        InlineKeyboardButton(text="❌ Отмена",      callback_data="cancel"),
    )
    return kb


# ── My bookings ────────────────────────────────────────────────────────────────

def my_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for b in bookings:
        day = date.fromisoformat(b["date"])
        wd  = RU_DAYS[day.weekday()]
        mon = RU_MONTHS[day.month]
        kb.add(InlineKeyboardButton(
            text=f"{wd} {day.day} {mon} {b['time']} — {b['svc_name']}",
            callback_data=f"view_booking:{b['id']}",
        ))
    return kb


def booking_detail_kb(bid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancel_booking:{bid}"))
    kb.add(InlineKeyboardButton(text="⬅️ Назад",           callback_data="back:my_bookings"))
    return kb


# ── Admin ──────────────────────────────────────────────────────────────────────

def admin_booking_kb(bid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text="✅ Выполнено", callback_data=f"admin_done:{bid}"),
        InlineKeyboardButton(text="❌ Отменить",  callback_data=f"admin_cancel:{bid}"),
    )
    return kb
