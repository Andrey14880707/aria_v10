"""München Barber — Telegram бот для записи. Запуск: python bot.py"""

import logging
from datetime import date
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

import config
import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
log = logging.getLogger(__name__)

bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

# ── FSM state per user: {user_id: {step, data}} ───────────────────────────────
STATE: dict[int, dict] = {}

def get_state(uid: int) -> dict:
    return STATE.get(uid, {})

def set_step(uid: int, step: str) -> None:
    STATE.setdefault(uid, {})["step"] = step

def upd(uid: int, **kwargs) -> None:
    STATE.setdefault(uid, {}).update(kwargs)

def clear(uid: int) -> None:
    STATE.pop(uid, None)

# ── Keyboards ──────────────────────────────────────────────────────────────────

RU_DAYS   = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
RU_MONTHS = ["","янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]

def fmt_date(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{RU_DAYS[d.weekday()]}, {d.day} {RU_MONTHS[d.month]}"

def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("✂️ Записаться"))
    kb.row(KeyboardButton("📋 Мои записи"), KeyboardButton("ℹ️ О нас"))
    return kb

def services_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for s in db.get_services():
        kb.add(InlineKeyboardButton(
            f"{s['name']} — {s['price']}€ ({s['duration']} мин)",
            callback_data=f"svc:{s['id']}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb

def masters_kb(sid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🎲 Любой мастер", callback_data=f"master:0:{sid}"))
    for m in db.get_masters():
        kb.add(InlineKeyboardButton(f"💈 {m['name']}", callback_data=f"master:{m['id']}:{sid}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:service"))
    return kb

def dates_kb(sid: int, mid: int, duration: int) -> InlineKeyboardMarkup:
    from datetime import timedelta
    kb = InlineKeyboardMarkup(row_width=2)
    today = date.today()
    found = 0
    for delta in range(config.DAYS_AHEAD):
        day = today + timedelta(days=delta)
        if mid == 0:
            has = db.any_master_has_slot(day, duration)
        else:
            has = bool(db.get_available_slots(mid, day, duration))
        if not has:
            continue
        d = date.fromisoformat(day.isoformat())
        kb.add(InlineKeyboardButton(
            f"{RU_DAYS[d.weekday()]}, {d.day} {RU_MONTHS[d.month]}",
            callback_data=f"date:{day.isoformat()}:{sid}:{mid}"))
        found += 1
    if not found:
        kb.add(InlineKeyboardButton("😔 Нет свободных дат", callback_data="noop"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:master"))
    return kb

def times_kb(slots: list, day_str: str, sid: int, mid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=3)
    for slot in slots:
        kb.add(InlineKeyboardButton(slot, callback_data=f"time:{slot}:{day_str}:{sid}:{mid}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:date"))
    return kb

def phone_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Поделиться номером", request_contact=True))
    kb.add(KeyboardButton("⏭ Пропустить"))
    return kb

def confirm_kb(sid: int, mid: int, day: str, t: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm:{sid}:{mid}:{day}:{t}"),
        InlineKeyboardButton("❌ Отмена",      callback_data="cancel"),
    )
    return kb

def my_bookings_kb(bookings: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for b in bookings:
        d = date.fromisoformat(b["date"])
        kb.add(InlineKeyboardButton(
            f"{RU_DAYS[d.weekday()]} {d.day} {RU_MONTHS[d.month]} {b['time']} — {b['svc_name']}",
            callback_data=f"view_booking:{b['id']}"))
    return kb

def booking_detail_kb(bid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("❌ Отменить запись", callback_data=f"cancel_booking:{bid}"))
    kb.add(InlineKeyboardButton("⬅️ Назад",           callback_data="back:my_bookings"))
    return kb

def admin_kb(bid: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Выполнено", callback_data=f"admin_done:{bid}"),
        InlineKeyboardButton("❌ Отменить",  callback_data=f"admin_cancel:{bid}"),
    )
    return kb

def summary(data: dict) -> str:
    return (
        f"📋 <b>Ваша запись:</b>\n\n"
        f"✂️ Услуга:  {data['svc_name']} ({data['duration']} мин)\n"
        f"💰 Цена:    {data['price']}€\n"
        f"💈 Мастер:  {data['master_name']}\n"
        f"📅 Дата:    {fmt_date(data['date'])}\n"
        f"🕐 Время:   {data['time']}\n"
        f"📱 Телефон: {data.get('phone') or 'не указан'}"
    )

# ── Message handlers ───────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    clear(msg.from_user.id)
    bot.send_message(msg.chat.id,
        f"✂️ Привет, <b>{msg.from_user.first_name}</b>! Добро пожаловать в <b>München Barber</b>.\n\n"
        "Выбери действие 👇", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "ℹ️ О нас")
def cmd_info(msg):
    bot.send_message(msg.chat.id,
        "💈 <b>München Barber</b>\n\n"
        "📍 Адрес: <i>укажите адрес</i>\n"
        "🕐 Пн–Сб: 10:00–20:00\n"
        "📞 Телефон: <i>укажите телефон</i>")

@bot.message_handler(func=lambda m: m.text == "✂️ Записаться")
def cmd_book(msg):
    uid = msg.from_user.id
    clear(uid)
    set_step(uid, "choose_service")
    bot.send_message(msg.chat.id, "🗓 Выбери услугу:", reply_markup=services_kb())

@bot.message_handler(func=lambda m: m.text == "📋 Мои записи")
def cmd_my(msg):
    bookings = db.get_user_bookings(msg.from_user.id)
    if not bookings:
        bot.send_message(msg.chat.id, "📋 Нет активных записей.", reply_markup=main_menu())
        return
    bot.send_message(msg.chat.id,
        f"📋 <b>Твои записи ({len(bookings)}):</b>",
        reply_markup=my_bookings_kb(bookings))

# Admin commands
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
    from datetime import timedelta
    _send_day(msg.chat.id, date.today() + timedelta(days=1))

def _send_day(chat_id: int, day: date):
    bookings = db.get_bookings_for_date(day.isoformat())
    header = f"📅 <b>{RU_DAYS[day.weekday()]}, {day.day} {RU_MONTHS[day.month]}</b> — {len(bookings)} записей"
    if not bookings:
        bot.send_message(chat_id, header + "\n\nЗаписей нет.")
        return
    bot.send_message(chat_id, header)
    for b in bookings:
        bot.send_message(chat_id,
            f"🕐 <b>{b['time']}</b> | 💈 {b['master_name']}\n"
            f"✂️ {b['svc_name']} ({b['duration']} мин, {b['price']}€)\n"
            f"👤 @{b['user_name'] or '—'} | 📱 {b['phone'] or '—'}\n"
            f"🔖 #{b['id']}",
            reply_markup=admin_kb(b["id"]))

@bot.message_handler(commands=["week"])
def cmd_week(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    bookings = db.get_upcoming_bookings(days=7)
    if not bookings:
        bot.send_message(msg.chat.id, "📭 Нет записей на 7 дней.")
        return
    by_date: dict = {}
    for b in bookings:
        by_date.setdefault(b["date"], []).append(b)
    lines = [f"📆 <b>Записи на 7 дней</b> (всего: {len(bookings)})\n"]
    for day_str, bs in sorted(by_date.items()):
        d = date.fromisoformat(day_str)
        lines.append(f"\n<b>{RU_DAYS[d.weekday()]}, {d.day} {RU_MONTHS[d.month]}</b>:")
        for b in bs:
            lines.append(f"  • {b['time']} {b['master_name']} — {b['svc_name']} | @{b['user_name'] or '—'}")
    bot.send_message(msg.chat.id, "\n".join(lines))

@bot.message_handler(commands=["stats"])
def cmd_stats(msg):
    if msg.from_user.id not in config.ADMIN_IDS: return
    bookings = db.get_upcoming_bookings(days=30)
    bot.send_message(msg.chat.id,
        f"📊 <b>Следующие 30 дней</b>\n\n"
        f"📋 Записей: {len(bookings)}\n"
        f"💰 Выручка: {sum(b['price'] for b in bookings)}€")

# Phone step
@bot.message_handler(content_types=["contact"])
def on_contact(msg):
    uid = msg.from_user.id
    if get_state(uid).get("step") != "enter_phone": return
    upd(uid, phone=msg.contact.phone_number)
    _show_confirm(msg.chat.id, uid)

@bot.message_handler(func=lambda m: m.text in ("⏭ Пропустить",) and
                     get_state(m.from_user.id).get("step") == "enter_phone")
def on_phone_skip(msg):
    uid = msg.from_user.id
    upd(uid, phone=None)
    _show_confirm(msg.chat.id, uid)

@bot.message_handler(func=lambda m: get_state(m.from_user.id).get("step") == "enter_phone")
def on_phone_text(msg):
    uid = msg.from_user.id
    upd(uid, phone=msg.text.strip())
    _show_confirm(msg.chat.id, uid)

def _show_confirm(chat_id: int, uid: int):
    data = get_state(uid)
    set_step(uid, "confirm")
    bot.send_message(chat_id, summary(data) + "\n\n<b>Всё верно?</b>",
        reply_markup=confirm_kb(data["service_id"], data["master_id"], data["date"], data["time"]))
    bot.send_message(chat_id, "👆", reply_markup=ReplyKeyboardRemove())

# ── Callback handlers ──────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: True)
def on_callback(cb):
    uid  = cb.from_user.id
    data = cb.data
    cid  = cb.message.chat.id
    mid  = cb.message.message_id
    st   = get_state(uid)

    def edit(text, kb=None):
        bot.edit_message_text(text, cid, mid, reply_markup=kb, parse_mode="HTML")

    # ── Services ──
    if data.startswith("svc:") and st.get("step") == "choose_service":
        sid = int(data.split(":")[1])
        svc = db.get_service(sid)
        if not svc:
            bot.answer_callback_query(cb.id, "Не найдено")
            return
        upd(uid, service_id=sid, svc_name=svc["name"], duration=svc["duration"], price=svc["price"])
        set_step(uid, "choose_master")
        edit(f"Услуга: <b>{svc['name']}</b>\n\nВыбери мастера:", masters_kb(sid))

    # ── Master ──
    elif data.startswith("master:") and st.get("step") == "choose_master":
        parts = data.split(":")
        m_id, sid = int(parts[1]), int(parts[2])
        name = "Любой мастер" if m_id == 0 else db.get_master(m_id)["name"]
        upd(uid, master_id=m_id, master_name=name)
        set_step(uid, "choose_date")
        edit(f"Мастер: <b>{name}</b>\n\nВыбери дату:",
             dates_kb(sid, m_id, st["duration"]))

    # ── Date ──
    elif data.startswith("date:") and st.get("step") == "choose_date":
        _, day_str, sid, m_id = data.split(":")
        sid, m_id = int(sid), int(m_id)
        if m_id == 0:
            best, best_n = None, 0
            for m in db.get_masters():
                slots = db.get_available_slots(m["id"], date.fromisoformat(day_str), st["duration"])
                if len(slots) > best_n:
                    best_n, best = len(slots), m
            if not best:
                bot.answer_callback_query(cb.id, "Нет мастеров", show_alert=True)
                return
            m_id = best["id"]
            upd(uid, master_id=m_id, master_name=best["name"])
        slots = db.get_available_slots(m_id, date.fromisoformat(day_str), st["duration"])
        if not slots:
            bot.answer_callback_query(cb.id, "Нет слотов", show_alert=True)
            return
        upd(uid, date=day_str)
        set_step(uid, "choose_time")
        edit(f"📅 <b>{fmt_date(day_str)}</b>\n\nВыбери время:",
             times_kb(slots, day_str, sid, m_id))

    # ── Time ──
    elif data.startswith("time:") and st.get("step") == "choose_time":
        parts    = data.split(":")
        time_str = f"{parts[1]}:{parts[2]}"
        day_str  = parts[3]
        m_id     = int(parts[5])
        if m_id != st.get("master_id"):
            m = db.get_master(m_id)
            upd(uid, master_id=m_id, master_name=m["name"] if m else "—")
        upd(uid, time=time_str)
        set_step(uid, "enter_phone")
        edit(f"🕐 Время: <b>{time_str}</b>\n\nПоделись номером (необязательно):")
        bot.send_message(cid, "👇 Нажми кнопку или введи вручную:", reply_markup=phone_kb())

    # ── Confirm ──
    elif data.startswith("confirm:") and st.get("step") == "confirm":
        parts    = data.split(":")
        sid, m_id = int(parts[1]), int(parts[2])
        day_str   = parts[3]
        time_str  = f"{parts[4]}:{parts[5]}"
        slots = db.get_available_slots(m_id, date.fromisoformat(day_str), st["duration"])
        if time_str not in slots:
            bot.answer_callback_query(cb.id, "😔 Это время уже занято!", show_alert=True)
            clear(uid)
            return
        bid = db.create_booking(
            user_id=uid, user_name=cb.from_user.username or cb.from_user.full_name,
            phone=st.get("phone"), master_id=m_id, service_id=sid,
            day=day_str, time=time_str)
        clear(uid)
        edit(f"🎉 <b>Запись подтверждена!</b>\n\n" + summary(st) +
             f"\n\n🔖 Номер записи: #{bid}\n\nЖдём тебя!")
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu())
        bot.answer_callback_query(cb.id, "✅ Готово!")
        # Notify admins
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id,
                    f"🔔 <b>Новая запись #{bid}</b>\n\n"
                    f"👤 @{cb.from_user.username or '—'} ({cb.from_user.full_name})\n"
                    f"📱 {st.get('phone') or '—'}\n"
                    f"✂️ {st['svc_name']} ({st['duration']} мин, {st['price']}€)\n"
                    f"💈 {st['master_name']}\n"
                    f"📅 {fmt_date(day_str)}  🕐 {time_str}",
                    reply_markup=admin_kb(bid))
            except Exception:
                pass
        return

    # ── My bookings ──
    elif data.startswith("view_booking:"):
        bid = int(data.split(":")[1])
        b = db.get_booking(bid)
        if not b or b["user_id"] != uid:
            bot.answer_callback_query(cb.id, "Не найдено", show_alert=True)
            return
        edit(f"📋 <b>Запись #{b['id']}</b>\n\n"
             f"✂️ {b['svc_name']} ({b['duration']} мин)\n"
             f"💰 {b['price']}€\n"
             f"💈 {b['master_name']}\n"
             f"📅 {fmt_date(b['date'])}  🕐 {b['time']}\n"
             f"📱 {b['phone'] or '—'}",
             booking_detail_kb(bid))

    elif data.startswith("cancel_booking:"):
        bid = int(data.split(":")[1])
        ok = db.cancel_booking(bid, uid)
        if ok:
            edit(f"❌ Запись #{bid} отменена.")
            bot.answer_callback_query(cb.id, "Отменено")
        else:
            bot.answer_callback_query(cb.id, "Ошибка", show_alert=True)

    elif data == "back:my_bookings":
        bookings = db.get_user_bookings(uid)
        if bookings:
            edit(f"📋 <b>Твои записи ({len(bookings)}):</b>", my_bookings_kb(bookings))
        else:
            edit("📋 Нет активных записей.")

    # ── Admin actions ──
    elif data.startswith("admin_done:"):
        if uid not in config.ADMIN_IDS:
            bot.answer_callback_query(cb.id, "Нет доступа", show_alert=True)
            return
        bid = int(data.split(":")[1])
        b   = db.get_booking(bid)
        if db.mark_done(bid):
            edit(cb.message.text + "\n\n✅ <b>Выполнено</b>")
            if b:
                try: bot.send_message(b["user_id"], f"✅ Спасибо за визит! Ждём снова! ✂️")
                except: pass
            bot.answer_callback_query(cb.id, "Отмечено")

    elif data.startswith("admin_cancel:"):
        if uid not in config.ADMIN_IDS:
            bot.answer_callback_query(cb.id, "Нет доступа", show_alert=True)
            return
        bid = int(data.split(":")[1])
        b   = db.get_booking(bid)
        if db.admin_cancel_booking(bid):
            edit(cb.message.text + "\n\n❌ <b>Отменено</b>")
            if b:
                try: bot.send_message(b["user_id"], f"😔 Запись #{bid} отменена мастером.")
                except: pass
            bot.answer_callback_query(cb.id, "Отменено")

    # ── Back navigation ──
    elif data.startswith("back:"):
        target = data.split(":")[1]
        if target == "service":
            set_step(uid, "choose_service")
            edit("Выбери услугу:", services_kb())
        elif target == "master":
            set_step(uid, "choose_master")
            edit("Выбери мастера:", masters_kb(st.get("service_id", 0)))
        elif target == "date":
            set_step(uid, "choose_date")
            edit("Выбери дату:", dates_kb(st.get("service_id", 0), st.get("master_id", 0), st.get("duration", 30)))

    elif data == "cancel":
        clear(uid)
        edit("❌ Запись отменена.")
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu())

    elif data == "noop":
        pass

    bot.answer_callback_query(cb.id)


# ── Run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    log.info("München Barber bot started")
    bot.infinity_polling()
