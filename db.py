# db.py
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import DB_FILE
from utils import now_str


class MemoryDB:
    def __init__(self, path: Path = DB_FILE):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init()

    def _init(self) -> None:
        with self.lock, self.conn:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    summary TEXT DEFAULT '',
                    message_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    source TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tool_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    tool_name TEXT NOT NULL,
                    command TEXT,
                    result TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, id);
                CREATE INDEX IF NOT EXISTS idx_facts_fact ON facts(fact);
                CREATE INDEX IF NOT EXISTS idx_notes_created_at ON notes(created_at);
                CREATE INDEX IF NOT EXISTS idx_tool_events_session_id ON tool_events(session_id, id);
                """
            )

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.lock:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key = ?",
                (key,),
            ).fetchone()
            return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO meta(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def start_session(self) -> int:
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions(started_at) VALUES (?)",
                (now_str(),),
            )
            return int(cur.lastrowid)

    def end_session(self, session_id: int, summary: str = "") -> None:
        with self.lock, self.conn:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            msg_count = int(row["c"]) if row else 0

            self.conn.execute(
                """
                UPDATE sessions
                SET ended_at = ?, summary = ?, message_count = ?
                WHERE id = ?
                """,
                (now_str(), summary, msg_count, session_id),
            )

    def add_message(self, session_id: int, role: str, content: str) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO messages(session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, now_str()),
            )

    def save_message(self, role: str, content: str, session_id: Optional[int] = None) -> None:
        if session_id is None:
            session_id = self._get_latest_session_id()
            if session_id is None:
                session_id = self.start_session()

        self.add_message(session_id, role, content)

    def recent_messages(self, limit: int = 20, session_id: Optional[int] = None) -> List[Dict[str, str]]:
        with self.lock:
            if session_id is None:
                rows = self.conn.execute(
                    """
                    SELECT role, content
                    FROM messages
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """
                    SELECT role, content
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                ).fetchall()

        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def history(self, limit: int = 20, session_id: Optional[int] = None) -> List[Dict[str, str]]:
        return self.recent_messages(limit=limit, session_id=session_id)

    def recent_sessions(self, limit: int = 3) -> List[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def sessions_count(self) -> int:
        with self.lock:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()
            return int(row["c"]) if row else 0

    def add_fact(self, fact: str, source: str = "") -> bool:
        fact = fact.strip()
        if not fact:
            return False

        try:
            with self.lock, self.conn:
                self.conn.execute(
                    """
                    INSERT INTO facts(fact, created_at, source)
                    VALUES (?, ?, ?)
                    """,
                    (fact, now_str(), source),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def search_facts(self, query: str, limit: int = 10) -> List[sqlite3.Row]:
        q = f"%{query.lower()}%"
        with self.lock:
            return self.conn.execute(
                """
                SELECT * FROM facts
                WHERE lower(fact) LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (q, limit),
            ).fetchall()

    def facts_count(self) -> int:
        with self.lock:
            row = self.conn.execute("SELECT COUNT(*) AS c FROM facts").fetchone()
            return int(row["c"]) if row else 0

    def add_note(self, note: str) -> None:
        note = note.strip()
        if not note:
            return

        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO notes(note, created_at)
                VALUES (?, ?)
                """,
                (note, now_str()),
            )

    def recent_notes(self, limit: int = 20) -> List[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM notes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def search_notes(self, query: str, limit: int = 20) -> List[sqlite3.Row]:
        q = f"%{query.lower()}%"
        with self.lock:
            return self.conn.execute(
                """
                SELECT * FROM notes
                WHERE lower(note) LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (q, limit),
            ).fetchall()

    def add_tool_event(
        self,
        session_id: Optional[int],
        tool_name: str,
        command: str,
        result: str,
        status: str,
    ) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO tool_events(session_id, tool_name, command, result, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, tool_name, command, result, status, now_str()),
            )

    def recent_tool_events(self, limit: int = 20) -> List[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM tool_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def stats(self) -> Dict[str, Any]:
        with self.lock:
            sessions = self.conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
            messages = self.conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
            facts = self.conn.execute("SELECT COUNT(*) AS c FROM facts").fetchone()["c"]
            notes = self.conn.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
            tools = self.conn.execute("SELECT COUNT(*) AS c FROM tool_events").fetchone()["c"]

        return {
            "sessions": int(sessions),
            "messages": int(messages),
            "facts": int(facts),
            "notes": int(notes),
            "tool_events": int(tools),
        }

    def _get_latest_session_id(self) -> Optional[int]:
        with self.lock:
            row = self.conn.execute(
                "SELECT id FROM sessions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return int(row["id"]) if row else None
