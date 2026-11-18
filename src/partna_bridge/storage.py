from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from typing import Any

SCHEMA = """
create table if not exists outbox (
  id integer primary key autoincrement,
  event_id text not null unique,
  path text not null,
  payload text not null,
  status text not null default 'pending',
  attempts integer not null default 0,
  next_attempt_at real not null,
  last_error text not null default '',
  created_at real not null
);
create index if not exists outbox_due on outbox (status, next_attempt_at);

create table if not exists inbox (
  event_id text primary key,
  payload text not null,
  received_at real not null
);
"""


class Store:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("pragma journal_mode=wal")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    async def enqueue(self, event_id: str, path: str, payload: dict[str, Any]) -> bool:
        now = time.time()
        async with self._lock:
            cursor = self._conn.execute(
                "insert or ignore into outbox "
                "(event_id, path, payload, next_attempt_at, created_at) "
                "values (?, ?, ?, ?, ?)",
                (event_id, path, json.dumps(payload, ensure_ascii=False), now, now),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    async def due(self, limit: int = 20) -> list[dict[str, Any]]:
        now = time.time()
        async with self._lock:
            rows = self._conn.execute(
                "select id, event_id, path, payload, attempts from outbox "
                "where status = 'pending' and next_attempt_at <= ? "
                "order by id limit ?",
                (now, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    async def mark_sent(self, entry_id: int) -> None:
        async with self._lock:
            self._conn.execute(
                "update outbox set status = 'sent', last_error = '' where id = ?",
                (entry_id,),
            )
            self._conn.commit()

    async def mark_failed(self, entry_id: int, attempts: int, error: str) -> None:
        delay = min(60 * 2 ** max(attempts - 1, 0), 3600)
        async with self._lock:
            self._conn.execute(
                "update outbox set attempts = ?, next_attempt_at = ?, last_error = ? "
                "where id = ?",
                (attempts, time.time() + delay, error[:300], entry_id),
            )
            self._conn.commit()

    async def retry(self, entry_id: int) -> bool:
        async with self._lock:
            cursor = self._conn.execute(
                "update outbox set status = 'pending', next_attempt_at = ? "
                "where id = ?",
                (time.time(), entry_id),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    async def list_outbox(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self._lock:
            rows = self._conn.execute(
                "select id, event_id, path, status, attempts, last_error, created_at "
                "from outbox order by id desc limit ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def save_inbox(self, event_id: str, payload: dict[str, Any]) -> bool:
        async with self._lock:
            cursor = self._conn.execute(
                "insert or ignore into inbox (event_id, payload, received_at) "
                "values (?, ?, ?)",
                (event_id, json.dumps(payload, ensure_ascii=False), time.time()),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    async def list_inbox(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self._lock:
            rows = self._conn.execute(
                "select event_id, received_at from inbox order by received_at desc "
                "limit ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
