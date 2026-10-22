"""
Login rate limiting: after LOGIN_MAX_FAILURES failed attempts within
LOGIN_WINDOW_SECONDS for the same email or the same client address, further
attempts are refused (429, Retry-After) until the window expires. A successful
login clears the email's counter.

Redis is used when REDIS_URL is set (shared between API processes); otherwise an
in-process counter. Defaults: 5 failures per 900 s.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Protocol, cast


def max_failures() -> int:
    return int(os.environ.get("LOGIN_MAX_FAILURES", "5"))


def window_seconds() -> int:
    return int(os.environ.get("LOGIN_WINDOW_SECONDS", "900"))


class Limiter(Protocol):
    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again (0 = allowed)."""

    def fail(self, key: str) -> None: ...

    def clear(self, key: str) -> None: ...

    def reset(self) -> None: ...


class MemoryLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def _recent(self, key: str, now: float) -> list[float]:
        hits = [t for t in self._hits.get(key, []) if now - t < window_seconds()]
        self._hits[key] = hits
        return hits

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            hits = self._recent(key, now)
            if len(hits) < max_failures():
                return 0
            return max(1, int(window_seconds() - (now - hits[0])) + 1)

    def fail(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._recent(key, now).append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisLimiter:
    """Fixed window per key: INCR + EXPIRE on the first failure."""

    def __init__(self, url: str) -> None:
        import redis

        self._r = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        self._prefix = "fraudsim:login:"

    def retry_after(self, key: str) -> int:
        k = self._prefix + key
        count = int(cast(Any, self._r.get(k)) or 0)
        if count < max_failures():
            return 0
        ttl = int(cast(Any, self._r.ttl(k)))
        return max(1, ttl)

    def fail(self, key: str) -> None:
        k = self._prefix + key
        pipe = self._r.pipeline()
        pipe.incr(k)
        pipe.expire(k, window_seconds(), nx=True)
        pipe.execute()

    def clear(self, key: str) -> None:
        self._r.delete(self._prefix + key)

    def reset(self) -> None:
        for k in self._r.scan_iter(self._prefix + "*"):
            self._r.delete(k)


_memory = MemoryLimiter()
_redis: dict[str, RedisLimiter] = {}


def limiter() -> Limiter:
    url = os.environ.get("REDIS_URL")
    if not url:
        return _memory
    if url not in _redis:
        _redis[url] = RedisLimiter(url)
    return _redis[url]
