from __future__ import annotations

import hashlib
import hmac
import time
from collections import deque


def verify_signature(secret: str, raw_body: bytes, header: str) -> bool:
    if not secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[len("sha256=") :], expected)


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        bucket = self._hits.setdefault(key, deque())
        while bucket and bucket[0] <= moment - self._window:
            bucket.popleft()
        if len(bucket) >= self._limit:
            return False
        bucket.append(moment)
        return True


class SeenEvents:
    def __init__(self, size: int = 2048) -> None:
        self._size = size
        self._seen: deque[str] = deque()
        self._index: set[str] = set()

    def add(self, event_id: str) -> bool:
        if event_id in self._index:
            return False
        self._index.add(event_id)
        self._seen.append(event_id)
        if len(self._seen) > self._size:
            self._index.discard(self._seen.popleft())
        return True
