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


# ── Init ───────────────────────────────────────────────────────────────────────

def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS masters (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT    NOT NULL,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS services (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            duration INTEGER NOT NULL,
            price    INTEGER NOT NULL,
            active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS working_hours (
            master_id  INTEGER NOT NULL,
            weekday    INTEGER NOT NULL,   -- 0=Mon … 6=Sun
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
            date       TEXT    NOT NULL,   -- YYYY-MM-DD
            time       TEXT    NOT NULL,   -- HH:MM
            status     TEXT    DEFAULT 'active',  -- active / cancelled / done
            created_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (master_id)  REFERENCES masters(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        );
        """)

        # Seed default data on first run
        if conn.execute("SELECT COUNT(*) FROM masters").fetchone()[0] == 0:
            conn.execute("INSERT INTO masters (name) VALUES ('Алексей')")
            conn.execute("INSERT INTO masters (name) VALUES ('Максим')")

        if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            for name, dur, price in [
                ("✂️ Стрижка",             45, 35),
                ("🧔 Борода",               30, 20),
                ("✂️🧔 Стрижка + борода",   75, 50),
                ("👦 Детская стрижка",      30, 25),
            ]:
                conn.execute(
                    "INSERT INTO services (name, duration, price) VALUES (?,?,?)",
                    (name, dur, price),
                )

        if conn.execute("SELECT COUNT(*) FROM working_hours").fetchone()[0] == 0:
            for mid in (1, 2):
                for day in range(6):  # Пн–Сб
                    conn.execute(
                        "INSERT INTO working_hours VALUES (?,?,?,?)",
                        (mid, day, "10:00", "20:00"),
                    )

        conn.commit()


# ── Masters ────────────────────────────────────────────────────────────────────

def get_masters(active_only: bool = True) -> list[sqlite3.Row]:
    with _conn() as conn:
        q = "SELECT * FROM masters"
        if active_only:
            q += " WHERE active=1"
        return conn.execute(q + " ORDER BY name").fetchall()


def get_master(mid: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM masters WHERE id=?", (mid,)).fetchone()


# ── Services ───────────────────────────────────────────────────────────────────

def get_services(active_only: bool = True) -> list[sqlite3.Row]:
    with _conn() as conn:
        q = "SELECT * FROM services"
        if active_only:
            q += " WHERE active=1"
        return conn.execute(q + " ORDER BY price").fetchall()


def get_service(sid: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM services WHERE id=?", (sid,)).fetchone()


# ── Available slots ────────────────────────────────────────────────────────────

def _time_to_min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _min_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def get_available_slots(master_id: int, day: date, duration: int) -> list[str]:
    """Return sorted list of HH:MM slots available for given master/date/service."""
    weekday = day.weekday()
    with _conn() as conn:
        wh = conn.execute(
            "SELECT start_time, end_time FROM working_hours WHERE master_id=? AND weekday=?",
            (master_id, weekday),
        ).fetchone()
        if not wh:
            return []

        start = _time_to_min(wh["start_time"])
        end   = _time_to_min(wh["end_time"])

        # Booked slots for that master/date
        booked = conn.execute(
            """SELECT b.time, s.duration
               FROM bookings b JOIN services s ON b.service_id=s.id
               WHERE b.master_id=? AND b.date=? AND b.status='active'""",
            (master_id, day.isoformat()),
        ).fetchall()

    # Build busy ranges
    busy: list[tuple[int, int]] = []
    for row in booked:
        t = _time_to_min(row["time"])
        busy.append((t, t + row["duration"]))

    slots = []
    cursor = start
    now_min = None
    if day == date.today():
        n = datetime.now()
        now_min = n.hour * 60 + n.minute + 30  # buffer 30 min

    while cursor + duration <= end:
        if now_min and cursor < now_min:
            cursor += config.SLOT_STEP
            continue
        # Check overlap with busy
        ok = all(cursor >= b_end or cursor + duration <= b_start for b_start, b_end in busy)
        if ok:
            slots.append(_min_to_time(cursor))
        cursor += config.SLOT_STEP

    return slots


def any_master_has_slot(day: date, duration: int) -> bool:
    """Check if at least one master has any free slot on this day."""
    for m in get_masters():
        if get_available_slots(m["id"], day, duration):
            return True
    return False


# ── Bookings ───────────────────────────────────────────────────────────────────

def create_booking(
    user_id: int,
    user_name: Optional[str],
    phone: Optional[str],
    master_id: int,
    service_id: int,
    day: str,
    time: str,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO bookings (user_id,user_name,phone,master_id,service_id,date,time)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, user_name, phone, master_id, service_id, day, time),
        )
        conn.commit()
        return cur.lastrowid


def get_user_bookings(user_id: int) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name,
                      s.duration, s.price
               FROM bookings b
               JOIN masters  m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.user_id=? AND b.status='active' AND b.date >= date('now')
               ORDER BY b.date, b.time""",
            (user_id,),
        ).fetchall()


def get_booking(bid: int) -> Optional[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name,
                      s.duration, s.price
               FROM bookings b
               JOIN masters  m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.id=?""",
            (bid,),
        ).fetchone()


def cancel_booking(bid: int, user_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE bookings SET status='cancelled' WHERE id=? AND user_id=? AND status='active'",
            (bid, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def admin_cancel_booking(bid: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE bookings SET status='cancelled' WHERE id=? AND status='active'",
            (bid,),
        )
        conn.commit()
        return cur.rowcount > 0


def mark_done(bid: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE bookings SET status='done' WHERE id=? AND status='active'",
            (bid,),
        )
        conn.commit()
        return cur.rowcount > 0


def get_bookings_for_date(day: str) -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name,
                      s.duration, s.price
               FROM bookings b
               JOIN masters  m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.date=? AND b.status='active'
               ORDER BY b.time, m.name""",
            (day,),
        ).fetchall()


def get_upcoming_bookings(days: int = 7) -> list[sqlite3.Row]:
    end = (date.today() + timedelta(days=days)).isoformat()
    with _conn() as conn:
        return conn.execute(
            """SELECT b.*, m.name AS master_name, s.name AS svc_name,
                      s.duration, s.price
               FROM bookings b
               JOIN masters  m ON b.master_id=m.id
               JOIN services s ON b.service_id=s.id
               WHERE b.date BETWEEN date('now') AND ?
                 AND b.status='active'
               ORDER BY b.date, b.time""",
            (end,),
        ).fetchall()
