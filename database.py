#!/usr/bin/env python3
"""
Userbot — Database Layer

Uses ONE persistent SQLite connection (guarded by a lock) instead of opening
a new connection on every call — the hot path needs this to stay fast.
All DB access happens on the asyncio event-loop thread, so a single
connection is safe.
"""

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

DATA_DIR: Path = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH: str = str(DATA_DIR / "userbot.db")

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def get_db() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
        return _conn


def close_db() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


def init_db() -> None:
    conn = get_db()
    with _lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_string TEXT NOT NULL UNIQUE,
                phone TEXT DEFAULT '',
                user_id INTEGER UNIQUE,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at REAL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_user_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL DEFAULT (strftime('%s','now'))
            );

            CREATE INDEX IF NOT EXISTS idx_history_acc_sender
                ON history (account_user_id, sender_id, id);

            CREATE TABLE IF NOT EXISTS blocked_users (
                account_user_id INTEGER NOT NULL,
                blocked_uid INTEGER NOT NULL,
                PRIMARY KEY (account_user_id, blocked_uid)
            );
            """
        )

        # Migrate the old global "enabled" key to "global_enabled"
        # (must run BEFORE inserting defaults so the old value survives)
        row = conn.execute("SELECT value FROM settings WHERE key='enabled'").fetchone()
        if row and not conn.execute(
            "SELECT 1 FROM settings WHERE key='global_enabled'"
        ).fetchone():
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('global_enabled', ?)",
                (row["value"],),
            )
        conn.execute("DELETE FROM settings WHERE key='enabled'")

        # Default settings
        defaults: Dict[str, str] = {
            "global_enabled": "true",
            "persona": config.DEFAULT_PERSONA,
            "paid_stars": str(config.DEFAULT_PAID_STARS),
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )

        # Clean up legacy one-shot flow flags from older versions
        conn.execute("DELETE FROM settings WHERE key LIKE 'awaiting_%'")

        conn.commit()


# ── Generic key-value ──

def setting_get(key: str, default: str = "") -> str:
    conn = get_db()
    with _lock:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def setting_set(key: str, value: str) -> None:
    conn = get_db()
    with _lock:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        conn.commit()


# ── Account CRUD ──

def account_add(
    session_string: str,
    user_id: int,
    first_name: str,
    username: str = "",
    phone: str = "",
) -> int:
    conn = get_db()
    with _lock:
        conn.execute(
            """INSERT OR IGNORE INTO accounts
               (session_string, phone, user_id, username, first_name, is_active)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (session_string, phone, user_id, username, first_name),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM accounts WHERE user_id=?", (user_id,)).fetchone()
    return row["id"] if row else 0


def account_remove(user_id: int) -> None:
    conn = get_db()
    with _lock:
        conn.execute("DELETE FROM accounts WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM history WHERE account_user_id=?", (user_id,))
        conn.execute("DELETE FROM blocked_users WHERE account_user_id=?", (user_id,))
        conn.commit()


def account_set_active(user_id: int, active: bool) -> None:
    conn = get_db()
    with _lock:
        conn.execute(
            "UPDATE accounts SET is_active=? WHERE user_id=?", (1 if active else 0, user_id)
        )
        conn.commit()


def account_get_all() -> List[Dict[str, Any]]:
    conn = get_db()
    with _lock:
        rows = conn.execute(
            "SELECT user_id, first_name, username, is_active FROM accounts"
        ).fetchall()
    return [
        {
            "user_id": r["user_id"],
            "first_name": r["first_name"] or "Unknown",
            "username": r["username"] or "",
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]


def account_get_session(user_id: int) -> Optional[str]:
    conn = get_db()
    with _lock:
        row = conn.execute(
            "SELECT session_string FROM accounts WHERE user_id=?", (user_id,)
        ).fetchone()
    return row["session_string"] if row else None


# ── History ──

def history_append(account_user_id: int, sender_id: int, role: str, content: str) -> None:
    conn = get_db()
    with _lock:
        conn.execute(
            "INSERT INTO history (account_user_id, sender_id, role, content) VALUES (?, ?, ?, ?)",
            (account_user_id, sender_id, role, content),
        )
        # Trim old entries: keep only (MAX_HISTORY_TURNS * 2) per sender per account
        max_entries = config.MAX_HISTORY_TURNS * 2
        conn.execute(
            """DELETE FROM history WHERE id IN (
                SELECT id FROM history
                WHERE account_user_id=? AND sender_id=?
                ORDER BY id DESC
                LIMIT -1 OFFSET ?
            )""",
            (account_user_id, sender_id, max_entries),
        )
        conn.commit()


def history_get(account_user_id: int, sender_id: int) -> List[Dict[str, str]]:
    max_entries = config.MAX_HISTORY_TURNS * 2
    conn = get_db()
    with _lock:
        rows = conn.execute(
            """SELECT role, content FROM history
               WHERE account_user_id=? AND sender_id=?
               ORDER BY id DESC LIMIT ?""",
            (account_user_id, sender_id, max_entries),
        ).fetchall()
    # Return in chronological order
    return [{"role": r["role"], "text": r["content"]} for r in reversed(rows)]


def history_clear(account_user_id: int, sender_id: int) -> None:
    conn = get_db()
    with _lock:
        conn.execute(
            "DELETE FROM history WHERE account_user_id=? AND sender_id=?",
            (account_user_id, sender_id),
        )
        conn.commit()


# ── Blocked users ──

def blocked_add(account_user_id: int, blocked_uid: int) -> None:
    conn = get_db()
    with _lock:
        conn.execute(
            "INSERT OR IGNORE INTO blocked_users (account_user_id, blocked_uid) VALUES (?, ?)",
            (account_user_id, blocked_uid),
        )
        conn.commit()


def blocked_remove(account_user_id: int, blocked_uid: int) -> None:
    conn = get_db()
    with _lock:
        conn.execute(
            "DELETE FROM blocked_users WHERE account_user_id=? AND blocked_uid=?",
            (account_user_id, blocked_uid),
        )
        conn.commit()


def blocked_is(account_user_id: int, blocked_uid: int) -> bool:
    conn = get_db()
    with _lock:
        row = conn.execute(
            "SELECT 1 FROM blocked_users WHERE account_user_id=? AND blocked_uid=?",
            (account_user_id, blocked_uid),
        ).fetchone()
    return row is not None


def blocked_count(account_user_id: int) -> int:
    conn = get_db()
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM blocked_users WHERE account_user_id=?",
            (account_user_id,),
        ).fetchone()
    return int(row["c"]) if row else 0
