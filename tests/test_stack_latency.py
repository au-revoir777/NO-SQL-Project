"""E8 metric helpers on hand-made inputs (docs/research/e8_protocol.md)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fraudsim.detectors.engine import BatchReport
from fraudsim.detectors.ensemble import RingUpdate
from fraudsim.experiments.stack_latency import (
    detect_ms,
    flagged,
    pct,
    schedule,
    summary,
    update_signature,
)
from fraudsim.types import Event, EventType, RingStatus

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_nearest_rank_percentiles() -> None:
    v = [5.0, 1.0, 4.0, 2.0, 3.0]
    assert pct(v, 50) == 3.0
    assert pct(v, 95) == 5.0 and pct(v, 99) == 5.0
    assert pct(v, 20) == 1.0 and pct(v, 21) == 2.0
    assert pct([], 50) is None
    s = summary([1.0, 2.0, 3.0, 4.0], "x")
    assert s == {"x_p50": 2.0, "x_p95": 4.0, "x_p99": 4.0, "x_n": 4}


def _upd(ring: str, change: str, members: list[str]) -> RingUpdate:
    return RingUpdate(T0, ring, change, RingStatus.CONFIRMED, tuple(members), ("hub_aware",), 0.9)


def _report(updates: list[RingUpdate], **timings: float) -> BatchReport:
    return BatchReport(
        batch=1,
        n_events=50,
        first_seq=1,
        last_seq=50,
        now=T0,
        touched=3,
        region=3,
        timings_ms=dict(timings),
        detector_ms={"hub_aware": 2.0, "temporal_cycle": 1.0},
        candidates={},
        updates=updates,
    )


def test_detect_time_matches_e4_and_signatures_compare_updates() -> None:
    r = _report([_upd("R1", "created", ["b", "a"])], ingest=9.0, dirty=1.5, view=0.5)
    assert detect_ms(r) == 5.0  # dirty + view + detectors; ingest excluded
    a = [r, _report([_upd("R1", "confirmed", ["a", "b"]), _upd("R2", "alert", ["c", "d"])])]
    b = [r, _report([_upd("R1", "confirmed", ["b", "a"]), _upd("R2", "alert", ["d", "c"])])]
    assert update_signature(a) == update_signature(b)  # member order does not matter
    assert flagged(a) == {("R1", ("a", "b")), ("R2", ("c", "d"))}
    c = [r, _report([_upd("R2", "alert", ["c", "d"]), _upd("R1", "confirmed", ["a", "b"])])]
    assert update_signature(a) != update_signature(c)  # order does
    assert flagged(a) == flagged(c)


def _ev(seq: int, at: float) -> Event:
    payload: dict[str, Any] = {"user_id": f"u{seq}"}
    return Event(f"e{seq}", EventType.USER_JOIN, T0 + timedelta(seconds=at), payload, "t", seq)


def test_paced_schedule_follows_simulated_time() -> None:
    evs = [_ev(1, 0.0), _ev(2, 0.5), _ev(3, 2.0)]
    assert schedule(evs, 1.0) == [0.0, 0.5, 2.0]
    assert schedule(evs, 2.0) == pytest.approx([0.0, 0.25, 1.0])
    assert schedule([], 1.0) == []
