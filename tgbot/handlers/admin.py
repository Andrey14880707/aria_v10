"""Admin commands — only for users listed in ADMIN_IDS."""

from datetime import date, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.filters.base import Filter

import config
import db
import keyboards as kb
from keyboards import RU_DAYS, RU_MONTHS, fmt_date

router = Router()


class IsAdmin(Filter):
    async def __call__(self, obj) -> bool:
        uid = getattr(obj, "from_user", None)
        if uid is None:
            return False
        return uid.id in config.ADMIN_IDS


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ── /admin — menu ──────────────────────────────────────────────────────────────

ADMIN_HELP = (
    "🛠 <b>Админ-панель München Barber</b>\n\n"
    "/today — записи на сегодня\n"
    "/tomorrow — записи на завтра\n"
    "/week — записи на 7 дней\n"
    "/stats — статистика\n"
)


@router.message(Command("admin"))
async def cmd_admin(msg: Message) -> None:
    await msg.answer(ADMIN_HELP, parse_mode="HTML")


# ── /today ─────────────────────────────────────────────────────────────────────

@router.message(Command("today"))
async def cmd_today(msg: Message) -> None:
    await _send_day_bookings(msg, date.today())


@router.message(Command("tomorrow"))
async def cmd_tomorrow(msg: Message) -> None:
    await _send_day_bookings(msg, date.today() + timedelta(days=1))


async def _send_day_bookings(msg: Message, day: date) -> None:
    bookings = db.get_bookings_for_date(day.isoformat())
    wd  = RU_DAYS[day.weekday()]
    mon = RU_MONTHS[day.month]
    header = f"📅 <b>{wd}, {day.day} {mon}</b> — {len(bookings)} записей\n"

    if not bookings:
        await msg.answer(header + "\nЗаписей нет.", parse_mode="HTML")
        return

    await msg.answer(header, parse_mode="HTML")
    for b in bookings:
        text = (
            f"🕐 <b>{b['time']}</b> | 💈 {b['master_name']}\n"
            f"✂️ {b['svc_name']} ({b['duration']} мин, {b['price']}€)\n"
            f"👤 @{b['user_name'] or '—'} | 📱 {b['phone'] or '—'}\n"
            f"🔖 #{b['id']}"
        )
        await msg.answer(text, reply_markup=kb.admin_booking_kb(b["id"]), parse_mode="HTML")


# ── /week ──────────────────────────────────────────────────────────────────────

@router.message(Command("week"))
async def cmd_week(msg: Message) -> None:
    bookings = db.get_upcoming_bookings(days=7)
    if not bookings:
        await msg.answer("📭 Нет записей на ближайшие 7 дней.")
        return

    # Group by date
    by_date: dict[str, list] = {}
    for b in bookings:
        by_date.setdefault(b["date"], []).append(b)

    lines = [f"📆 <b>Записи на 7 дней</b> (всего: {len(bookings)})\n"]
    for day_str, bs in sorted(by_date.items()):
        day = date.fromisoformat(day_str)
        wd  = RU_DAYS[day.weekday()]
        mon = RU_MONTHS[day.month]
        lines.append(f"\n<b>{wd}, {day.day} {mon}</b> ({len(bs)} записей):")
        for b in bs:
            lines.append(f"  • {b['time']} {b['master_name']} — {b['svc_name']} | @{b['user_name'] or '—'}")

    await msg.answer("\n".join(lines), parse_mode="HTML")


# ── /stats ─────────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(msg: Message) -> None:
    bookings = db.get_upcoming_bookings(days=30)
    total_price = sum(b["price"] for b in bookings)
    await msg.answer(
        f"📊 <b>Статистика (следующие 30 дней)</b>\n\n"
        f"📋 Записей: {len(bookings)}\n"
        f"💰 Выручка: {total_price}€",
        parse_mode="HTML",
    )


# ── Admin actions on bookings ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_done:"))
async def admin_done(cb: CallbackQuery, bot: Bot) -> None:
    bid = int(cb.data.split(":")[1])
    b = db.get_booking(bid)
    ok = db.mark_done(bid)
    if ok:
        await cb.message.edit_text(
            cb.message.text + "\n\n✅ <b>Отмечено как выполнено</b>",
            parse_mode="HTML",
        )
        # Notify client
        if b:
            try:
                await bot.send_message(
                    b["user_id"],
                    f"✅ Спасибо за визит! Твоя запись #{bid} в München Barber завершена.\n"
                    "Будем рады видеть тебя снова! ✂️",
                )
            except Exception:
                pass
        await cb.answer("Отмечено как выполнено")
    else:
        await cb.answer("Не удалось обновить", show_alert=True)


@router.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel(cb: CallbackQuery, bot: Bot) -> None:
    bid = int(cb.data.split(":")[1])
    b = db.get_booking(bid)
    ok = db.admin_cancel_booking(bid)
    if ok:
        await cb.message.edit_text(
            cb.message.text + "\n\n❌ <b>Запись отменена</b>",
            parse_mode="HTML",
        )
        # Notify client
        if b:
            try:
                await bot.send_message(
                    b["user_id"],
                    f"😔 К сожалению, твоя запись #{bid} в München Barber отменена мастером.\n"
                    "Пожалуйста, запишись на другое время.",
                )
            except Exception:
                pass
        await cb.answer("Запись отменена")
    else:
        await cb.answer("Не удалось отменить", show_alert=True)
