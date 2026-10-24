"""Fixed-window rate limiting behind a small interface.

Redis is used for shared counters when configured. It is *only* a throttle; it is never used as
an authorization store (see docs/SECURITY.md).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

import redis

logger = logging.getLogger("coresync.ratelimit")


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult: ...


class InMemoryRateLimiter:
    """Per-process limiter for development and tests. Not shared across instances."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, tuple[int, int]] = {}  # key -> (window_bucket, count)

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        bucket = now // window_seconds
        retry_after = window_seconds - (now % window_seconds)
        with self._lock:
            stored_bucket, count = self._counters.get(key, (bucket, 0))
            if stored_bucket != bucket:
                count = 0
            count += 1
            self._counters[key] = (bucket, count)
            if len(self._counters) > 50_000:  # bound memory
                self._counters = {k: v for k, v in self._counters.items() if v[0] == bucket}
        allowed = count <= limit
        return RateLimitResult(allowed, max(limit - count, 0), 0 if allowed else retry_after)


class RedisRateLimiter:
    def __init__(self, client: redis.Redis, fallback: RateLimiter | None = None) -> None:
        self._client = client
        self._fallback = fallback or InMemoryRateLimiter()

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = int(time.time())
        bucket = now // window_seconds
        retry_after = window_seconds - (now % window_seconds)
        redis_key = f"rl:{key}:{bucket}"
        try:
            pipe = self._client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds + 1)
            count = int(pipe.execute()[0])
        except redis.RedisError:
            # Degrade to a local limiter rather than failing requests or disabling throttling.
            logger.warning("Redis unavailable for rate limiting; using in-memory fallback")
            return self._fallback.hit(key, limit, window_seconds)
        allowed = count <= limit
        return RateLimitResult(allowed, max(limit - count, 0), 0 if allowed else retry_after)


def build_redis_client(url: str | None) -> redis.Redis | None:
    if not url:
        return None
    return redis.Redis.from_url(url, socket_timeout=1.0, socket_connect_timeout=1.0)


def build_rate_limiter(client: redis.Redis | None) -> RateLimiter:
    return RedisRateLimiter(client) if client is not None else InMemoryRateLimiter()
