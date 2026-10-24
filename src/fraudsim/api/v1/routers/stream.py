"""
/api/v1/stream: Server-Sent Events from the live-run streams (P3).

Each event carries the stream entry id (`id:`), so a reconnecting EventSource
sends `Last-Event-ID` and resumes right after the last entry it saw: no gap and
no duplicate. On a first connection `?since=` gives the starting id (default:
only new entries); `?run_id=` keeps one run's entries. A comment line is sent
every 15 s of silence so proxies keep the connection open. The response ends
when the session's access token expires; the client refreshes and reconnects
with its Last-Event-ID.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from fraudsim.api.v1.auth.security import ACCESS_COOKIE, decode_token
from fraudsim.api.v1.schemas import ErrorEnvelope
from fraudsim.api.v1.schemas.stream import AlertV1, RunMetricsV1
from fraudsim.api.v1.stream.hub import ALERTS, METRICS, hub

router = APIRouter(prefix="/stream", tags=["stream"])

HEARTBEAT_S = 15.0
ID_PATTERN = r"^(\$|\d+-\d+)$"


class EventStreamResponse(StreamingResponse):
    """text/event-stream; the documented 200 model is the payload of each `data:` line."""

    media_type = "text/event-stream"


def sse_responses(model: type) -> dict[int | str, dict[str, Any]]:
    return {
        200: {"model": model, "description": "event-stream; each `data:` line is one such object"},
        422: {"model": ErrorEnvelope, "description": "Invalid id"},
    }


def _start_id(request: Request, since: str) -> str:
    last = request.headers.get("last-event-id", "").strip()
    return last if last and last.replace("-", "").isdigit() else since


async def _events(
    request: Request, stream: str, event: str, start: str, run_id: str | None
) -> AsyncIterator[str]:
    claims = decode_token(request.cookies.get(ACCESS_COOKIE, ""), "access")
    after = await hub().last_id(stream) if start == "$" else start
    yield "retry: 3000\n\n"
    while not await request.is_disconnected():
        remaining = (claims.expires_at - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return  # session expired: the client refreshes and reconnects
        block = int(min(HEARTBEAT_S, remaining) * 1000)
        entries = await hub().read(stream, after, block_ms=block)
        if not entries:
            yield ": keep-alive\n\n"
            continue
        for entry_id, payload in entries:
            after = entry_id
            if run_id is not None and payload.get("run_id") != run_id:
                continue
            yield f"id: {entry_id}\nevent: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _sse(
    request: Request, stream: str, event: str, since: str, run_id: str | None
) -> EventStreamResponse:
    return EventStreamResponse(
        _events(request, stream, event, _start_id(request, since), run_id),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/alerts",
    operation_id="stream_alerts",
    response_class=EventStreamResponse,
    responses=sse_responses(AlertV1),
    summary="SSE of alerts and early warnings (event `alert`)",
)
async def stream_alerts(
    request: Request,
    since: str = Query("$", pattern=ID_PATTERN, description="Start after this id; $ = new only"),
    run_id: str | None = Query(None, max_length=64),
) -> EventStreamResponse:
    return _sse(request, ALERTS, "alert", since, run_id)


@router.get(
    "/metrics",
    operation_id="stream_metrics",
    response_class=EventStreamResponse,
    responses=sse_responses(RunMetricsV1),
    summary="SSE of KPI samples (event `metrics`)",
)
async def stream_metrics(
    request: Request,
    since: str = Query("$", pattern=ID_PATTERN, description="Start after this id; $ = new only"),
    run_id: str | None = Query(None, max_length=64),
) -> EventStreamResponse:
    return _sse(request, METRICS, "metrics", since, run_id)
