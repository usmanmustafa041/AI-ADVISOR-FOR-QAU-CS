"""Operational database (SQLite, WAL): settings, admins, conversations, feedback, logs.

SQLite in WAL mode comfortably serves a department-scale chatbot (thousands of students,
read-mostly, a few writes per question). All access goes through :class:`Database` so the
backing store can move to PostgreSQL later without touching callers.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    is_secret   INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_by  TEXT
);
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    last_login_at TEXT,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until  REAL
);
CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    admin_id   INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    meta            TEXT
);
CREATE INDEX IF NOT EXISTS messages_conv ON messages(conversation_id, created_at);
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY,
    message_id  TEXT NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating IN (-1, 1)),
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(message_id)
);
CREATE TABLE IF NOT EXISTS query_log (
    id           INTEGER PRIMARY KEY,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    message_id   TEXT,
    question     TEXT NOT NULL,
    language     TEXT,
    outcome      TEXT NOT NULL,       -- answered | abstained | smalltalk | refused | error | cached
    provider     TEXT,
    model        TEXT,
    latency_ms   INTEGER,
    ttft_ms      INTEGER,
    top_score    REAL,
    sources      TEXT,
    index_build  TEXT,
    error        TEXT
);
CREATE INDEX IF NOT EXISTS query_log_time ON query_log(created_at);
CREATE TABLE IF NOT EXISTS timetable_state (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    doc        TEXT NOT NULL,
    version    INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    updated_by TEXT
);
CREATE TABLE IF NOT EXISTS timetable_audit (
    id      INTEGER PRIMARY KEY,
    at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    actor   TEXT,
    action  TEXT NOT NULL,
    detail  TEXT,
    before  TEXT NOT NULL,
    undone  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    finished_at TEXT,
    detail      TEXT
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Additive, idempotent schema upgrades for databases created by earlier versions."""
        def columns(table: str) -> set[str]:
            return {r["name"] for r in self._conn().execute(f"PRAGMA table_info({table})")}

        wanted = {
            "conversations": [("owner_id", "TEXT"), ("title", "TEXT")],
            "feedback": [("reason", "TEXT")],
        }
        for table, cols in wanted.items():
            have = columns(table)
            for name, typ in cols:
                if name not in have:
                    self._conn().execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
        self._conn().execute("CREATE INDEX IF NOT EXISTS conv_owner ON conversations(owner_id, updated_at)")

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            self._local.conn = conn
        return conn

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self._conn().execute(sql, tuple(params))

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: Iterable[Any] = (), default=None):
        row = self.one(sql, params)
        return row[0] if row and row[0] is not None else default
