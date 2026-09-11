"""Redis-backed rate limiting that degrades gracefully without Redis.

Fixed-window counter in Redis when reachable. If Redis is unconfigured,
unreachable, or errors mid-request, falls back to an in-process counter
(per-worker, resets on restart) rather than failing the request or
letting it through unlimited-and-unnoticed -- a warning is logged once.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("engine_api.ratelimit")

try:
    from redis import asyncio as redis_asyncio
except ImportError:  # pragma: no cover - redis is a declared dependency
    redis_asyncio = None  # type: ignore[assignment]


class RateLimiter:
    def __init__(self, redis_url: str | None, limit: int, window_seconds: int) -> None:
        self._redis_url = redis_url
        self._limit = limit
        self._window = window_seconds
        self._client = None
        self._warned = False
        self._memory: dict[str, tuple[int, int]] = {}  # key -> (count, window_id)

    async def _get_client(self):
        if not self._redis_url or redis_asyncio is None:
            return None
        if self._client is None:
            self._client = redis_asyncio.from_url(
                self._redis_url, socket_connect_timeout=0.5, socket_timeout=0.5
            )
        try:
            await self._client.ping()
            return self._client
        except Exception:
            if not self._warned:
                logger.warning(
                    "redis unavailable for rate limiting; degrading to in-process limiter"
                )
                self._warned = True
            return None

    async def allow(self, key: str) -> bool:
        """Returns True if `key` is still within its window budget."""
        now = time.time()
        window_id = int(now // self._window)
        client = await self._get_client()

        if client is not None:
            redis_key = f"ratelimit:{key}:{window_id}"
            try:
                count = await client.incr(redis_key)
                if count == 1:
                    await client.expire(redis_key, self._window)
                return count <= self._limit
            except Exception:
                logger.warning("redis error during rate-limit check; falling back in-process")

        count, stored_window = self._memory.get(key, (0, window_id))
        if stored_window != window_id:
            count = 0
            stored_window = window_id
        count += 1
        self._memory[key] = (count, stored_window)
        return count <= self._limit
