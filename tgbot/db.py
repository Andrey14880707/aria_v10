"""SQLite database for München Barber bot."""

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import config

DB_PATH = Path(__file__).parent / "barber.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS masters (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name   TEXT    NOT NULL,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS services (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            emoji    TEXT    NOT NULL DEFAULT '✂️',
            category TEXT    NOT NULL DEFAULT 'Стрижка',
            duration INTEGER NOT NULL,
            price    INTEGER NOT NULL,
            active   INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS working_hours (
            master_id  INTEGER NOT NULL,
            weekday    INTEGER NOT NULL,
            start_time TEXT    NOT NULL DEFAULT '10:00',
            end_time   TEXT    NOT NULL DEFAULT '20:00',
            PRIMARY KEY (master_id, weekday)
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            user_name  TEXT,
            phone      TEXT,
            master_id  INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            date       TEXT    NOT NULL,
            time       TEXT    NOT NULL,
            status     TEXT    DEFAULT 'active',
            created_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (master_id)  REFERENCES masters(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        );
        """)

        if conn.execute("SELECT COUNT(*) FROM masters").fetchone()[0] == 0:
            conn.execute("INSERT INTO masters (name) VALUES ('Мишаня')")

        if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            services = [
                # (name, emoji, category, duration, price)
                ("Стрижка",                   "✂️",  "Стрижка", 45, 35),
                ("Стрижка + укладка",         "✂️💧", "Стрижка", 60, 45),
                ("Детская стрижка (до 12 л)", "👦",  "Стрижка", 30, 25),
                ("Борода — оформление",       "🧔",  "Борода",  30, 25),
                ("Борода — бритьё",           "🪒",  "Борода",  45, 35),
                ("Стрижка + борода",          "🔥",  "Комбо",   75, 55),
                ("Стрижка + борода + укладка","💎",  "Комбо",   90, 65),
            ]
            for name, emoji, cat, dur, price in services:
                conn.execute(
                    "INSERT INTO services (name,emoji,category,duration,price) VALUES (?,?,?,?,?)",
                    (name, emoji, cat, dur, price))

        if conn.execute("SELECT COUNT(*) FROM working_hours").fetchone()[0] == 0:
            for day in range(6):  # Пн–Сб
                conn.execute("INSERT INTO working_hours VALUES (?,?,?,?)", (1, day, "10:00", "20:00"))

        conn.commit()


# ── Masters ────────────────────────────────────────────────────────────────────

def get_master(mid: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM masters WHERE id=?", (mid,)).fetchone()

def get_masters(active_only: bool = True) -> list:
    with _conn() as conn:
        q = "SELECT * FROM masters" + (" WHERE active=1" if active_only else "")
        return conn.execute(q).fetchall()


# ── Services ───────────────────────────────────────────────────────────────────

def get_services() -> list:
    with _conn() as conn:
        return conn.execute("SELECT * FROM services WHERE active=1 ORDER BY category,price").fetchall()

def get_service(sid: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()


# ── Slots ──────────────────────────────────────────────────────────────────────

def _t2m(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m

def _m2t(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"

def get_available_slots(master_id: int, day: date, duration: int) -> list:
    weekday = day.weekday()
    with _conn() as conn:
        wh = conn.execute(
            "SELECT start_time, end_time FROM working_hours WHERE master_id=? AND weekday=?",
            (master_id, weekday)).fetchone()
        if not wh:
            return []
        booked = conn.execute(
            """SELECT b.time, s.duration FROM bookings b
               JOIN services s ON b.service_id=s.id
               WHERE b.master_id=? AND b.date=? AND b.status='active'""",
            (master_id, day.isoformat())).fetchall()

    start, end = _t2m(wh["start_time"]), _t2m(wh["end_time"])
    busy = [(_t2m(r["time"]), _t2m(r["time"]) + r["duration"]) for r in booked]

    now_min = None
    if day == date.today():
        n = datetime.now()
        now_min = n.hour * 60 + n.minute + 30

    slots, cur = [], start
    while cur + duration <= end:
        if now_min and cur < now_min:
            cur += config.SLOT_STEP
            continue
        if all(cur >= b_end or cur + duration <= b_start for b_start, b_end in busy):
            slots.append(_m2t(cur))
        cur += config.SLOT_STEP
    return slots

def has_slot(master_id: int, day: date, duration: int) -> bool:
    return bool(get_available_slots(master_id, day, duration))


# ── Bookings ───────────────────────────────────────────────────────────────────

def create_booking(user_id, user_name, phone, master_id, service_id, day, time) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO bookings (user_id,user_name,phone,master_id,service_id,date,time) VALUES (?,?,?,?,?,?,?)",
            (user_id, user_name, phone, master_id, service_id, day, time))
        conn.commit()
        return cur.lastrowid

def get_user_bookings(user_id: int) -> list:
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name, s.emoji,
                      s.duration, s.price
               FROM bookings b JOIN masters m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.user_id=? AND b.status='active' AND b.date >= date('now')
               ORDER BY b.date, b.time""", (user_id,)).fetchall()

def get_booking(bid: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name, s.emoji,
                      s.duration, s.price
               FROM bookings b JOIN masters m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.id=?""", (bid,)).fetchone()

def cancel_booking(bid: int, user_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE bookings SET status='cancelled' WHERE id=? AND user_id=? AND status='active'",
            (bid, user_id))
        conn.commit()
        return cur.rowcount > 0

def admin_cancel_booking(bid: int) -> bool:
    with _conn() as conn:
        cur = conn.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND status='active'", (bid,))
        conn.commit()
        return cur.rowcount > 0

def mark_done(bid: int) -> bool:
    with _conn() as conn:
        cur = conn.execute("UPDATE bookings SET status='done' WHERE id=? AND status='active'", (bid,))
        conn.commit()
        return cur.rowcount > 0

def get_bookings_for_date(day: str) -> list:
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name,
                      s.duration, s.price
               FROM bookings b JOIN masters m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.date=? AND b.status='active' ORDER BY b.time""", (day,)).fetchall()

def get_upcoming_bookings(days: int = 7) -> list:
    end = (date.today() + timedelta(days=days)).isoformat()
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name,
                      s.duration, s.price
               FROM bookings b JOIN masters m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.date BETWEEN date('now') AND ? AND b.status='active'
               ORDER BY b.date, b.time""", (end,)).fetchall()
