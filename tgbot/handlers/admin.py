"""Admin commands (aiogram 2.x)."""

from datetime import date, timedelta

from aiogram import Dispatcher, Bot
from aiogram.types import Message, CallbackQuery

import config
import db
import keyboards as kb
from keyboards import RU_DAYS, RU_MONTHS, fmt_date


def _is_admin(uid: int) -> bool:
    return uid in config.ADMIN_IDS


ADMIN_HELP = (
    "🛠 <b>Админ-панель München Barber</b>\n\n"
    "/today — записи на сегодня\n"
    "/tomorrow — записи на завтра\n"
    "/week — записи на 7 дней\n"
    "/stats — статистика\n"
)


async def cmd_admin(msg: Message) -> None:
    if not _is_admin(msg.from_user.id): return
    await msg.answer(ADMIN_HELP)


async def cmd_today(msg: Message) -> None:
    if not _is_admin(msg.from_user.id): return
    await _send_day(msg, date.today())


async def cmd_tomorrow(msg: Message) -> None:
    if not _is_admin(msg.from_user.id): return
    await _send_day(msg, date.today() + timedelta(days=1))


async def _send_day(msg: Message, day: date) -> None:
    bookings = db.get_bookings_for_date(day.isoformat())
    header = f"📅 <b>{RU_DAYS[day.weekday()]}, {day.day} {RU_MONTHS[day.month]}</b> — {len(bookings)} записей"
    if not bookings:
        await msg.answer(header + "\n\nЗаписей нет.")
        return
    await msg.answer(header)
    for b in bookings:
        await msg.answer(
            f"🕐 <b>{b['time']}</b> | 💈 {b['master_name']}\n"
            f"✂️ {b['svc_name']} ({b['duration']} мин, {b['price']}€)\n"
            f"👤 @{b['user_name'] or '—'} | 📱 {b['phone'] or '—'}\n"
            f"🔖 #{b['id']}",
            reply_markup=kb.admin_booking_kb(b["id"]),
        )


async def cmd_week(msg: Message) -> None:
    if not _is_admin(msg.from_user.id): return
    bookings = db.get_upcoming_bookings(days=7)
    if not bookings:
        await msg.answer("📭 Нет записей на 7 дней.")
        return
    by_date: dict = {}
    for b in bookings:
        by_date.setdefault(b["date"], []).append(b)
    lines = [f"📆 <b>Записи на 7 дней</b> (всего: {len(bookings)})\n"]
    for day_str, bs in sorted(by_date.items()):
        day = date.fromisoformat(day_str)
        lines.append(f"\n<b>{RU_DAYS[day.weekday()]}, {day.day} {RU_MONTHS[day.month]}</b>:")
        for b in bs:
            lines.append(f"  • {b['time']} {b['master_name']} — {b['svc_name']} | @{b['user_name'] or '—'}")
    await msg.answer("\n".join(lines))


async def cmd_stats(msg: Message) -> None:
    if not _is_admin(msg.from_user.id): return
    bookings = db.get_upcoming_bookings(days=30)
    await msg.answer(
        f"📊 <b>Следующие 30 дней</b>\n\n"
        f"📋 Записей: {len(bookings)}\n"
        f"💰 Выручка: {sum(b['price'] for b in bookings)}€"
    )


async def admin_done(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    bid = int(cb.data.split(":")[1])
    b   = db.get_booking(bid)
    ok  = db.mark_done(bid)
    if ok:
        await cb.message.edit_text(cb.message.text + "\n\n✅ <b>Выполнено</b>")
        if b:
            try:
                await Bot.get_current().send_message(
                    b["user_id"],
                    f"✅ Спасибо за визит! Запись #{bid} завершена. Ждём снова! ✂️"
                )
            except Exception:
                pass
        await cb.answer("Отмечено")
    else:
        await cb.answer("Ошибка", show_alert=True)


async def admin_cancel(cb: CallbackQuery) -> None:
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    bid = int(cb.data.split(":")[1])
    b   = db.get_booking(bid)
    ok  = db.admin_cancel_booking(bid)
    if ok:
        await cb.message.edit_text(cb.message.text + "\n\n❌ <b>Отменено</b>")
        if b:
            try:
                await Bot.get_current().send_message(
                    b["user_id"],
                    f"😔 Запись #{bid} отменена мастером. Пожалуйста, запишись на другое время."
                )
            except Exception:
                pass
        await cb.answer("Отменено")
    else:
        await cb.answer("Ошибка", show_alert=True)


def register(dp: Dispatcher) -> None:
    dp.register_message_handler(cmd_admin,    commands=["admin"])
    dp.register_message_handler(cmd_today,    commands=["today"])
    dp.register_message_handler(cmd_tomorrow, commands=["tomorrow"])
    dp.register_message_handler(cmd_week,     commands=["week"])
    dp.register_message_handler(cmd_stats,    commands=["stats"])
    dp.register_callback_query_handler(admin_done,   lambda c: c.data.startswith("admin_done:"))
    dp.register_callback_query_handler(admin_cancel, lambda c: c.data.startswith("admin_cancel:"))
