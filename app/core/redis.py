"""Redis client and distributed caching utilities with in-memory fallback when Redis is unreachable."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from loguru import logger
import redis.asyncio as aioredis

from app.core.config import settings


class _IN_MEMORY_REDIS_FALLBACK:
    """In-memory async Redis-compatible fallback used when Redis is unreachable in local/test environments."""

    def __init__(self) -> None:
        self._store : dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(
        self
        , key   : str
        , value : str
        , ex    : int | None = None
        , nx    : bool = False
    ) -> bool:
        if nx and key in self._store:
            return False
        self._store[key] = str(value)
        return True

    async def setex(self, key: str, time_sec: int, value: str) -> bool:
        self._store[key] = str(value)
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    async def incr(self, key: str) -> int:
        current          = int(self._store.get(key, "0")) + 1
        self._store[key] = str(current)
        return current

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                deleted += 1
        return deleted

    async def flushdb(self) -> bool:
        self._store.clear()
        return True

    async def aclose(self) -> None:
        pass


_redis_client    : aioredis.Redis | _IN_MEMORY_REDIS_FALLBACK | None = None
_fallback_client : _IN_MEMORY_REDIS_FALLBACK                         = _IN_MEMORY_REDIS_FALLBACK()
_use_fallback    : bool                                              = False


def get_redis_client() -> aioredis.Redis | _IN_MEMORY_REDIS_FALLBACK:
    """Get singleton Redis client instance (or in-memory fallback when Redis is unreachable in test/dev)."""
    global _redis_client
    if (
        _use_fallback
        or settings.ENV in ("testing", "test")
        or settings.ENVIRONMENT in ("testing", "test")
        or bool(os.getenv("PYTEST_CURRENT_TEST"))
    ):
        return _fallback_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
            max_connections=50,
            retry_on_timeout=False,
            retry=None,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis client gracefully."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as e:
            logger.warning(f"Error disconnecting Redis client: {e}")
        _redis_client = None


async def is_redis_available() -> bool:
    """Health check for Redis connectivity."""
    try:
        client = get_redis_client()
        return bool(await client.ping())
    except Exception as e:
        logger.warning(f"Redis ping failed: {e}")
        return False


async def redis_get(key: str) -> str | None:
    """Safely get string value from Redis; returns None on failure."""
    global _use_fallback
    try:
        client = get_redis_client()
        return await client.get(key)
    except Exception as e:
        logger.warning(f"Redis GET failed for key {key}: {e}")
        _use_fallback = True
        return await _fallback_client.get(key)


async def redis_set(key: str, value: str, ex: int | None = None) -> bool:
    """Safely set string value in Redis with optional TTL (seconds)."""
    global _use_fallback
    try:
        client = get_redis_client()
        await client.set(key, value, ex=ex)
        return True
    except Exception as e:
        logger.warning(f"Redis SET failed for key {key}: {e}")
        _use_fallback = True
        return await _fallback_client.set(key, value, ex=ex)


async def redis_incr(key: str) -> int:
    """Safely increment integer key in Redis; fallback to in-memory counter on failure."""
    global _use_fallback
    try:
        client = get_redis_client()
        return await client.incr(key)
    except Exception as e:
        logger.warning(f"Redis INCR failed for key {key}: {e}")
        _use_fallback = True
        return await _fallback_client.incr(key)


async def redis_delete(key: str) -> bool:
    """Safely delete a key from Redis."""
    global _use_fallback
    try:
        client = get_redis_client()
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis DELETE failed for key {key}: {e}")
        _use_fallback = True
        await _fallback_client.delete(key)
        return True


@asynccontextmanager
async def redis_distributed_lock(
    lock_key        : str
    , timeout       : int   = 10
    , wait_timeout  : float = 2.0
    , poll_interval : float = 0.05
) -> AsyncGenerator[bool, None]:
    """
    Acquire a distributed lock with TTL to prevent cache stampedes.
    Yields True if acquired, False if timed out waiting.
    Ensures safe release only if acquired.
    """
    client     = get_redis_client()
    lock_val   = "1"
    acquired   = False
    start_time = asyncio.get_event_loop().time()

    try:
        while True:
            try:
                is_set = await client.set(lock_key, lock_val, nx=True, ex=timeout)
                if is_set:
                    acquired = True
                    break
            except Exception as e:
                logger.warning(f"Redis lock error on {lock_key}: {e}")
                acquired = True
                break

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= wait_timeout:
                break
            await asyncio.sleep(poll_interval)

        yield acquired
    finally:
        if acquired:
            try:
                await client.delete(lock_key)
            except Exception as e:
                logger.warning(f"Failed to release lock {lock_key}: {e}")
