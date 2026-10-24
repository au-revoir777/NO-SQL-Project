"""
Append-only streams for the live dashboard (P3): `fraudsim:alerts`,
`fraudsim:metrics`, `fraudsim:events`.

With REDIS_URL set they are Redis Streams (XADD with approximate MAXLEN, XREAD
BLOCK), so several API workers and reconnecting browsers see one ordered log.
Without it, an in-process log with the same id semantics is used. Entry ids are
Redis-style "<ms>-<seq>" strings and strictly increasing within a stream; a
reader passes the last id it saw and gets everything after it, which is what
the SSE endpoints do with Last-Event-ID.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import deque
from typing import Any, Protocol, cast

ALERTS = "fraudsim:alerts"
METRICS = "fraudsim:metrics"
EVENTS = "fraudsim:events"
MAXLEN = {ALERTS: 10_000, METRICS: 5_000, EVENTS: 5_000}

Entry = tuple[str, dict[str, Any]]


def _id_key(entry_id: str) -> tuple[int, int]:
    ms, _, seq = entry_id.partition("-")
    return int(ms), int(seq or 0)


class StreamHub(Protocol):
    backend: str

    async def publish(self, stream: str, payload: dict[str, Any]) -> str: ...

    async def read(
        self, stream: str, after: str, block_ms: int, count: int = 500
    ) -> list[Entry]: ...

    async def last_id(self, stream: str) -> str: ...


class MemoryStreams:
    """
    In-process streams: a bounded deque per stream. Readers wait on an
    asyncio.Event of their own loop; publish wakes them thread-safely, so a
    publisher and readers may run on different event loops.
    """

    backend = "memory"

    def __init__(self) -> None:
        self._logs: dict[str, deque[Entry]] = {}
        self._waiters: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Event]]] = {}
        self._lock = threading.Lock()
        self._last: tuple[int, int] = (0, 0)

    def _log(self, stream: str) -> deque[Entry]:
        if stream not in self._logs:
            self._logs[stream] = deque(maxlen=MAXLEN.get(stream, 5_000))
            self._waiters[stream] = set()
        return self._logs[stream]

    def _next_id(self) -> str:
        ms = int(time.time() * 1000)
        last_ms, last_seq = self._last
        self._last = (ms, 0) if ms > last_ms else (last_ms, last_seq + 1)
        return f"{self._last[0]}-{self._last[1]}"

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        with self._lock:
            log = self._log(stream)
            entry_id = self._next_id()
            log.append((entry_id, payload))
            waiters = list(self._waiters[stream])
        for loop, event in waiters:
            loop.call_soon_threadsafe(event.set)
        return entry_id

    def _after(self, stream: str, after: str, count: int) -> list[Entry]:
        key = _id_key(after)
        with self._lock:
            return [e for e in self._log(stream) if _id_key(e[0]) > key][:count]

    async def read(self, stream: str, after: str, block_ms: int, count: int = 500) -> list[Entry]:
        got = self._after(stream, after, count)
        if got or block_ms <= 0:
            return got
        waiter = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            self._waiters[stream].add(waiter)
        try:
            # Re-check after registering, so an entry published in between is not missed.
            got = self._after(stream, after, count)
            if got:
                return got
            await asyncio.wait_for(waiter[1].wait(), timeout=block_ms / 1000)
        except TimeoutError:
            return []
        finally:
            with self._lock:
                self._waiters[stream].discard(waiter)
        return self._after(stream, after, count)

    async def last_id(self, stream: str) -> str:
        with self._lock:
            log = self._log(stream)
            return log[-1][0] if log else "0-0"


class RedisStreams:
    """Redis Streams backend (redis.asyncio)."""

    backend = "redis"

    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._client = cast(Any, aioredis.from_url(url, decode_responses=True))

    async def publish(self, stream: str, payload: dict[str, Any]) -> str:
        entry_id = await self._client.xadd(
            stream,
            {"data": json.dumps(payload, default=str)},
            maxlen=MAXLEN.get(stream, 5_000),
            approximate=True,
        )
        return str(entry_id)

    async def read(self, stream: str, after: str, block_ms: int, count: int = 500) -> list[Entry]:
        resp = await self._client.xread({stream: after}, count=count, block=block_ms or None)
        out: list[Entry] = []
        for _name, entries in resp or []:
            for entry_id, fields in entries:
                out.append((str(entry_id), json.loads(fields["data"])))
        return out

    async def last_id(self, stream: str) -> str:
        if not await self._client.exists(stream):
            return "0-0"
        info = await self._client.xinfo_stream(stream)
        return str(info["last-generated-id"])


_hub: StreamHub | None = None


def hub() -> StreamHub:
    """The process-wide hub: Redis when REDIS_URL is set, else in-process."""
    global _hub
    if _hub is None:
        url = os.environ.get("REDIS_URL")
        _hub = RedisStreams(url) if url else MemoryStreams()
    return _hub


def reset_hub(new: StreamHub | None = None) -> None:
    """Tests: replace or forget the process-wide hub."""
    global _hub
    _hub = new
