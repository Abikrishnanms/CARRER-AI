"""
Redis client — async Redis connection with connection pooling and helpers.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_client: Any = None


def get_redis_client() -> Any:
    """Get or create a singleton async Redis client."""
    global _client
    if _client is None:
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            password = os.getenv("REDIS_PASSWORD", "")
            _client = aioredis.from_url(
                redis_url,
                password=password or None,
                decode_responses=True,
                max_connections=20,
            )
            logger.info(f"Redis client created: {redis_url}")
        except ImportError:
            logger.warning("redis[asyncio] not installed — Redis features will be unavailable")
            _client = _NoopRedis()
    return _client


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _client
    if _client and not isinstance(_client, _NoopRedis):
        await _client.aclose()
        _client = None


class _NoopRedis:
    """No-op Redis stub when redis package is not installed."""

    async def get(self, key: str) -> None:
        return None

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        pass

    async def delete(self, *keys: str) -> int:
        return 0

    async def exists(self, *keys: str) -> int:
        return 0

    async def expire(self, key: str, seconds: int) -> bool:
        return False

    async def incr(self, key: str) -> int:
        return 0

    async def ping(self) -> bool:
        return False

    async def hset(self, name: str, mapping: dict[str, Any]) -> int:
        return 0

    async def hget(self, name: str, key: str) -> None:
        return None

    async def hgetall(self, name: str) -> dict:
        return {}

    async def lpush(self, name: str, *values: Any) -> int:
        return 0

    async def lrange(self, name: str, start: int, end: int) -> list:
        return []


# ─── Helper functions ─────────────────────────────────────────────────────────

async def cache_get(key: str) -> str | None:
    """Get a cached value by key."""
    redis = get_redis_client()
    return await redis.get(key)


async def cache_set(key: str, value: str, ttl_seconds: int = 300) -> None:
    """Set a cached value with TTL."""
    redis = get_redis_client()
    await redis.set(key, value, ex=ttl_seconds)


async def cache_delete(key: str) -> None:
    """Delete a cached value."""
    redis = get_redis_client()
    await redis.delete(key)


async def rate_limit_check(
    key: str,
    max_requests: int = 100,
    window_seconds: int = 60,
) -> tuple[bool, int]:
    """
    Simple sliding-window rate limiter.
    Returns (is_allowed, current_count).
    """
    redis = get_redis_client()
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    allowed = count <= max_requests
    return allowed, int(count)
