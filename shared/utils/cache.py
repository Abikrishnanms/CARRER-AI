"""
Tiny in-process TTL cache for hot analytics endpoints.

Avoids hitting Mongo for /analytics/overview (which scans the whole jobs
collection) on every page refresh. Survives within a single process; for
multi-worker deployments, Redis is preferred — see shared.redis.cache.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, ttl_seconds: int = 30, max_entries: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_compute(
        self,
        key: str,
        producer: Callable[[], Awaitable[T]],
    ) -> T:
        now = time.monotonic()
        cached = self._store.get(key)
        if cached is not None and (now - cached[0]) < self._ttl:
            return cached[1]

        async with self._lock:
            cached = self._store.get(key)
            if cached is not None and (now - cached[0]) < self._ttl:
                return cached[1]

            value = await producer()

            if len(self._store) >= self._max:
                oldest_key = min(self._store, key=lambda k: self._store[k][0])
                self._store.pop(oldest_key, None)

            self._store[key] = (now, value)
            return value

    def invalidate(self, key: str | None = None) -> None:
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)


_overview_cache = TTLCache(ttl_seconds=60)
_trends_cache = TTLCache(ttl_seconds=120)


def get_overview_cache() -> TTLCache:
    return _overview_cache


def get_trends_cache() -> TTLCache:
    return _trends_cache