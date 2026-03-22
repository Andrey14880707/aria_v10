"""München Barber — бот для записи. python bot.py"""

import logging
import threading
import time as _time
from datetime import date, timedelta
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

import config, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

MASTER_ID = 1  # Мишаня — единственный мастер

# ── FSM ────────────────────────────────────────────────────────────────────────
STATE: dict[int, dict] = {}

def st(uid): return STATE.get(uid, {})
def set_step(uid, step): STATE.setdefault(uid, {})["step"] = step
def upd(uid, **kw): STATE.setdefault(uid, {}).update(kw)
def clr(uid): STATE.pop(uid, None)

# ── Локализация ────────────────────────────────────────────────────────────────
RU_DAYS_S  = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
RU_DAYS_L  = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]
RU_MONTHS  = ["","январь","февраль","март","апрель","май","июнь",
               "июль","август","сентябрь","октябрь","ноябрь","декабрь"]
RU_MONTHS_R= ["","января","февраля","марта","апреля","мая","июня",
               "июля","августа","сентября","октября","ноября","декабря"]

def fmt_date(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{RU_DAYS_L[d.weekday()]}, {d.day} {RU_MONTHS_R[d.month]}"

def summary(data: dict) -> str:
    return (
        f"<b>Ваша запись:</b>\n\n"
        f"{data['emoji']}  <b>{data['svc_name']}</b>\n"
        f"⏱  {data['duration']} мин  ·  💰 {data['price']}€\n\n"
        f"📅  {fmt_date(data['date'])}\n"
        f"🕐  {data['time']}\n"
        f"💈  Мишаня\n"
        f"📱  {data.get('phone') or 'не указан'}"
    )

# ── Клавиатуры ─────────────────────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("✂️ Записаться"))
    kb.row(KeyboardButton("📋 Мои записи"), KeyboardButton("ℹ️ О нас"))
    return kb

def services_kb() -> InlineKeyboardMarkup:
    """Услуги сгруппированы по категориям."""
    kb = InlineKeyboardMarkup(row_width=1)
    services = db.get_services()
    cur_cat = None
    for s in services:
        if s["category"] != cur_cat:
            cur_cat = s["category"]
            icons = {"Стрижка":"✂️","Борода":"🧔","Комбо":"🔥"}.get(cur_cat, "")
            kb.add(InlineKeyboardButton(f"── {icons} {cur_cat} ──", callback_data="noop"))
        kb.add(InlineKeyboardButton(
            f"{s['emoji']}  {s['name']}  ·  {s['price']}€  ·  {s['duration']} мин",
            callback_data=f"svc:{s['id']}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb

def calendar_kb(service_id: int, duration: int) -> InlineKeyboardMarkup:
    """Календарь на 2 недели вперёд."""
    kb = InlineKeyboardMarkup(row_width=7)
    today = date.today()

    # Заголовок месяца
    kb.row(InlineKeyboardButton(
        f"📅  {RU_MONTHS[today.month].capitalize()}  {today.year}",
        callback_data="noop"))
    # Дни недели
    kb.row(*[InlineKeyboardButton(d, callback_data="noop") for d in RU_DAYS_S])

    # Начало с понедельника текущей недели
    monday = today - timedelta(days=today.weekday())
    for week in range(3):
        row = []
        for dow in range(7):
            day = monday + timedelta(weeks=week, days=dow)
            if day < today or day > today + timedelta(days=config.DAYS_AHEAD):
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            elif db.has_slot(MASTER_ID, day, duration):
                row.append(InlineKeyboardButton(
                    str(day.day),
                    callback_data=f"date:{day.isoformat()}:{service_id}"))
            else:
                row.append(InlineKeyboardButton("·", callback_data="noop"))
        kb.row(*row)

    kb.add(InlineKeyboardButton("⬅️ Назад к услугам", callback_data="back:service"))
    return kb

def times_kb(slots: list, day_str: str, sid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=4)
    btns = [InlineKeyboardButton(slot, callback_data=f"time:{slot}:{day_str}:{sid}") for slot in slots]
    kb.add(*btns)
    kb.add(InlineKeyboardButton("⬅️ Назад к календарю", callback_data=f"back:date:{sid}"))
    return kb

def phone_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Поделиться номером", request_contact=True))
    kb.add(KeyboardButton("⏭ Пропустить"))
    return kb

def confirm_kb(sid: int, day: str, t: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm:{sid}:{day}:{t}"),
        InlineKeyboardButton("❌ Отмена",      callback_data="cancel"),
    )
    return kb

def my_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for b in bookings:
        d = date.fromisoformat(b["date"])
        kb.add(InlineKeyboardButton(
            f"{b['emoji']} {RU_DAYS_S[d.weekday()]} {d.day} {RU_MONTHS_R[d.month]}  ·  {b['time']}  ·  {b['svc_name']}",
            callback_data=f"view_booking:{b['id']}"))
    return kb

def booking_detail_kb(bid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("❌ Отменить запись", callback_data=f"cancel_booking:{bid}"))
    kb.add(InlineKeyboardButton("⬅️ К списку",        callback_data="back:my_bookings"))
    return kb

def admin_kb(bid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Выполнено", callback_data=f"admin_done:{bid}"),
        InlineKeyboardButton("❌ Отменить",  callback_data=f"admin_cancel:{bid}"),
    )
    return kb

# ── Команды ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    clr(msg.from_user.id)
    bot.send_message(msg.chat.id,
        f"✂️ Привет, <b>{msg.from_user.first_name}</b>!\n\n"
        "Добро пожаловать в <b>München Barber</b> 💈\n"
        "Запишись на стрижку за пару нажатий 👇",
        reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "ℹ️ О нас")
def cmd_info(msg):
    bot.send_message(msg.chat.id,
        "💈 <b>München Barber</b>\n\n"
        "Профессиональная мужская стрижка в Мюнхене.\n\n"
        "📍 <i>укажите адрес</i>\n"
        "🕐 Пн–Сб · 10:00–20:00\n"
        "📞 <i>укажите телефон</i>\n"
        "📸 @MunchenBarberbot")

@bot.message_handler(func=lambda m: m.text == "✂️ Записаться")
def cmd_book(msg):
    uid = msg.from_user.id
    clr(uid); set_step(uid, "choose_service")
    bot.send_message(msg.chat.id,
        "Выбери услугу 👇\n\n"
        "<i>Цены указаны в евро · время в минутах</i>",
        reply_markup=services_kb())

@bot.message_handler(func=lambda m: m.text == "📋 Мои записи")
def cmd_my(msg):
    bookings = db.get_user_bookings(msg.from_user.id)
    if not bookings:
        bot.send_message(msg.chat.id,
            "📋 Нет активных записей.\n\nНажми <b>✂️ Записаться</b>!",
            reply_markup=main_menu())
        return
    bot.send_message(msg.chat.id,
        f"📋 <b>Твои записи ({len(bookings)})</b>\n\nВыбери для подробностей:",
        reply_markup=my_bookings_kb(bookings))

# Admin
@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    bot.send_message(msg.chat.id,
        "🛠 <b>Админ-панель</b>\n\n/today /tomorrow /week /stats")

@bot.message_handler(commands=["today"])
def cmd_today(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    _send_day(msg.chat.id, date.today())

@bot.message_handler(commands=["tomorrow"])
def cmd_tomorrow(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    _send_day(msg.chat.id, date.today() + timedelta(days=1))

@bot.message_handler(commands=["week"])
def cmd_week(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    bookings = db.get_upcoming_bookings(7)
    if not bookings:
        bot.send_message(msg.chat.id, "📭 Нет записей на 7 дней.")
        return
    by_date: dict = {}
    for b in bookings: by_date.setdefault(b["date"], []).append(b)
    lines = [f"📆 <b>Записи на 7 дней</b> · всего: {len(bookings)}\n"]
    for day_str, bs in sorted(by_date.items()):
        d = date.fromisoformat(day_str)
        lines.append(f"\n<b>{RU_DAYS_L[d.weekday()]}, {d.day} {RU_MONTHS_R[d.month]}</b>")
        for b in bs:
            lines.append(f"  🕐 {b['time']}  {b['svc_name']}  · @{b['user_name'] or '—'}")
    bot.send_message(msg.chat.id, "\n".join(lines))

@bot.message_handler(commands=["stats"])
def cmd_stats(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    bookings = db.get_upcoming_bookings(30)
    bot.send_message(msg.chat.id,
        f"📊 <b>Следующие 30 дней</b>\n\n"
        f"📋 Записей:  {len(bookings)}\n"
        f"💰 Выручка: {sum(b['price'] for b in bookings)}€")

def _send_day(chat_id: int, day: date):
    bookings = db.get_bookings_for_date(day.isoformat())
    hdr = f"📅 <b>{RU_DAYS_L[day.weekday()]}, {day.day} {RU_MONTHS_R[day.month]}</b> — {len(bookings)} записей"
    if not bookings:
        bot.send_message(chat_id, hdr + "\n\nЗаписей нет 🎉")
        return
    bot.send_message(chat_id, hdr)
    for b in bookings:
        bot.send_message(chat_id,
            f"🕐 <b>{b['time']}</b>  ·  {b['svc_name']} ({b['duration']} мин, {b['price']}€)\n"
            f"👤 @{b['user_name'] or '—'}  📱 {b['phone'] or '—'}\n"
            f"🔖 #{b['id']}",
            reply_markup=admin_kb(b["id"]))

# Phone step
@bot.message_handler(content_types=["contact"])
def on_contact(msg):
    uid = msg.from_user.id
    if st(uid).get("step") != "enter_phone": return
    upd(uid, phone=msg.contact.phone_number)
    _show_confirm(msg.chat.id, uid)

@bot.message_handler(func=lambda m: m.text == "⏭ Пропустить"
                     and st(m.from_user.id).get("step") == "enter_phone")
def on_skip(msg):
    upd(msg.from_user.id, phone=None)
    _show_confirm(msg.chat.id, msg.from_user.id)

@bot.message_handler(func=lambda m: st(m.from_user.id).get("step") == "enter_phone")
def on_phone(msg):
    upd(msg.from_user.id, phone=msg.text.strip())
    _show_confirm(msg.chat.id, msg.from_user.id)

def _show_confirm(chat_id: int, uid: int):
    data = st(uid)
    set_step(uid, "confirm")
    bot.send_message(chat_id,
        summary(data) + "\n\n<b>Всё верно?</b>",
        reply_markup=confirm_kb(data["service_id"], data["date"], data["time"]))
    bot.send_message(chat_id, "👆", reply_markup=ReplyKeyboardRemove())

# ── Callback ───────────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: True)
def on_cb(cb):
    uid = cb.from_user.id
    data = cb.data
    cid  = cb.message.chat.id
    mid  = cb.message.message_id
    s    = st(uid)

    def edit(text, kb=None):
        bot.edit_message_text(text, cid, mid, reply_markup=kb, parse_mode="HTML")

    # ── Услуга ──
    if data.startswith("svc:") and s.get("step") == "choose_service":
        sid = int(data.split(":")[1])
        svc = db.get_service(sid)
        if not svc:
            bot.answer_callback_query(cb.id, "Не найдено"); return
        upd(uid, service_id=sid, svc_name=svc["name"], emoji=svc["emoji"],
            duration=svc["duration"], price=svc["price"])
        set_step(uid, "choose_date")
        edit(
            f"<b>{svc['emoji']} {svc['name']}</b>\n"
            f"⏱ {svc['duration']} мин  ·  💰 {svc['price']}€\n\n"
            f"Выбери дату 👇",
            calendar_kb(sid, svc["duration"]))

    # ── Дата ──
    elif data.startswith("date:") and s.get("step") == "choose_date":
        parts = data.split(":")
        day_str, sid = parts[1], int(parts[2])
        slots = db.get_available_slots(MASTER_ID, date.fromisoformat(day_str), s["duration"])
        if not slots:
            bot.answer_callback_query(cb.id, "Нет свободных слотов", show_alert=True); return
        upd(uid, date=day_str)
        set_step(uid, "choose_time")
        edit(
            f"{s['emoji']} <b>{s['svc_name']}</b>\n"
            f"📅 <b>{fmt_date(day_str)}</b>\n\n"
            f"Выбери время 👇",
            times_kb(slots, day_str, sid))

    # ── Время ──
    elif data.startswith("time:") and s.get("step") == "choose_time":
        parts = data.split(":")
        time_str = f"{parts[1]}:{parts[2]}"
        day_str  = parts[3]
        upd(uid, time=time_str)
        set_step(uid, "enter_phone")
        edit(
            f"{s['emoji']} <b>{s['svc_name']}</b>\n"
            f"📅 {fmt_date(day_str)}  ·  🕐 <b>{time_str}</b>\n\n"
            "Поделись номером телефона — мастер сможет связаться при необходимости.\n"
            "<i>Или пропусти этот шаг.</i>")
        bot.send_message(cid, "👇", reply_markup=phone_kb())

    # ── Подтверждение ──
    elif data.startswith("confirm:") and s.get("step") == "confirm":
        parts    = data.split(":")
        sid      = int(parts[1])
        day_str  = parts[2]
        time_str = f"{parts[3]}:{parts[4]}"
        slots = db.get_available_slots(MASTER_ID, date.fromisoformat(day_str), s["duration"])
        if time_str not in slots:
            bot.answer_callback_query(cb.id, "😔 Это время уже занято!", show_alert=True)
            clr(uid); return
        bid = db.create_booking(
            user_id=uid, user_name=cb.from_user.username or cb.from_user.full_name,
            phone=s.get("phone"), master_id=MASTER_ID, service_id=sid,
            day=day_str, time=time_str)
        clr(uid)
        edit(
            f"🎉 <b>Запись подтверждена!</b>\n\n"
            + summary(s) +
            f"\n\n🔖 № {bid}\n\n"
            "До встречи! Если нужно отменить — нажми «📋 Мои записи».")
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu())
        bot.answer_callback_query(cb.id, "✅ Готово!")
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id,
                    f"🔔 <b>Новая запись #{bid}</b>\n\n"
                    f"👤 @{cb.from_user.username or '—'}  ({cb.from_user.full_name})\n"
                    f"📱 {s.get('phone') or '—'}\n"
                    f"{s['emoji']} {s['svc_name']}  ·  {s['duration']} мин  ·  {s['price']}€\n"
                    f"📅 {fmt_date(day_str)}  🕐 {time_str}",
                    reply_markup=admin_kb(bid))
            except: pass
        return

    # ── Мои записи ──
    elif data.startswith("view_booking:"):
        bid = int(data.split(":")[1])
        b = db.get_booking(bid)
        if not b or b["user_id"] != uid:
            bot.answer_callback_query(cb.id, "Не найдено", show_alert=True); return
        edit(
            f"📋 <b>Запись #{b['id']}</b>\n\n"
            f"{b['emoji']} <b>{b['svc_name']}</b>  ·  {b['duration']} мин  ·  {b['price']}€\n"
            f"📅 {fmt_date(b['date'])}  ·  🕐 {b['time']}\n"
            f"💈 Мишаня\n"
            f"📱 {b['phone'] or '—'}",
            booking_detail_kb(bid))

    elif data.startswith("cancel_booking:"):
        bid = int(data.split(":")[1])
        if db.cancel_booking(bid, uid):
            edit(f"❌ Запись #{bid} отменена.\n\nЖдём в следующий раз! ✂️")
            bot.answer_callback_query(cb.id, "Отменено")
        else:
            bot.answer_callback_query(cb.id, "Ошибка", show_alert=True)

    elif data == "back:my_bookings":
        bookings = db.get_user_bookings(uid)
        if bookings:
            edit(f"📋 <b>Твои записи ({len(bookings)})</b>", my_bookings_kb(bookings))
        else:
            edit("📋 Нет активных записей.")

    # ── Админ ──
    elif data.startswith("admin_done:"):
        if uid not in config.ADMIN_IDS:
            bot.answer_callback_query(cb.id, "Нет доступа", show_alert=True); return
        bid = int(data.split(":")[1])
        b = db.get_booking(bid)
        if db.mark_done(bid):
            edit(cb.message.text + "\n\n✅ <b>Выполнено</b>")
            if b:
                try: bot.send_message(b["user_id"], "✅ Спасибо за визит! Ждём снова в München Barber ✂️")
                except: pass
            bot.answer_callback_query(cb.id, "Отмечено")

    elif data.startswith("admin_cancel:"):
        if uid not in config.ADMIN_IDS:
            bot.answer_callback_query(cb.id, "Нет доступа", show_alert=True); return
        bid = int(data.split(":")[1])
        b = db.get_booking(bid)
        if db.admin_cancel_booking(bid):
            edit(cb.message.text + "\n\n❌ <b>Отменено мастером</b>")
            if b:
                try: bot.send_message(b["user_id"],
                    f"😔 Запись #{bid} отменена. Запишись на другое время!")
                except: pass
            bot.answer_callback_query(cb.id, "Отменено")

    # ── Назад ──
    elif data == "back:service":
        set_step(uid, "choose_service")
        edit("Выбери услугу 👇\n\n<i>Цены в евро · время в минутах</i>", services_kb())

    elif data.startswith("back:date:"):
        sid = int(data.split(":")[2])
        set_step(uid, "choose_date")
        edit(
            f"{s.get('emoji','')} <b>{s.get('svc_name','')}</b>\n\nВыбери дату 👇",
            calendar_kb(sid, s.get("duration", 30)))

    elif data == "cancel":
        clr(uid)
        edit("❌ Отменено.")
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu())

    elif data == "noop":
        pass

    bot.answer_callback_query(cb.id)


# ── Напоминания ────────────────────────────────────────────────────────────────

_reminded_ids: set[int] = set()

def _reminder_loop():
    """Каждую минуту проверяет записи через ~30 минут и отправляет напоминание."""
    while True:
        _time.sleep(60)
        try:
            for b in db.get_bookings_for_reminder():
                if b["id"] in _reminded_ids:
                    continue
                _reminded_ids.add(b["id"])
                try:
                    bot.send_message(
                        b["user_id"],
                        f"⏰ <b>Напоминание!</b>\n\n"
                        f"Через 30 минут — {b['emoji']} <b>{b['svc_name']}</b>\n"
                        f"🕐 {b['time']}  ·  💈 Мишаня\n\n"
                        "Ждём тебя! ✂️")
                except Exception as e:
                    log.warning("Reminder failed uid=%s: %s", b["user_id"], e)
        except Exception as e:
            log.error("Reminder loop error: %s", e)


if __name__ == "__main__":
    db.init_db()
    threading.Thread(target=_reminder_loop, daemon=True, name="reminder").start()
    log.info("München Barber bot started 💈")
    bot.infinity_polling()
