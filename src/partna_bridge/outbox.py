from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from .engine import EngineClient, EngineError
from .storage import Store

logger = logging.getLogger(__name__)


class OutboxWorker:
    def __init__(self, store: Store, engine: EngineClient, poll_seconds: float = 5.0) -> None:
        self._store = store
        self._engine = engine
        self._poll = poll_seconds
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("outbox loop failed")
            await asyncio.sleep(self._poll)

    async def run_once(self) -> int:
        sent = 0
        for entry in await self._store.due():
            payload = json.loads(entry["payload"])
            try:
                await self._engine.post(entry["path"], payload)
            except EngineError as error:
                await self._store.mark_failed(entry["id"], entry["attempts"] + 1, error.detail)
            else:
                await self._store.mark_sent(entry["id"])
                sent += 1
        return sent
