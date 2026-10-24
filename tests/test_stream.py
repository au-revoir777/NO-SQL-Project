"""
P3: live-run streams. The hub contract (both backends), SSE ordering and resume
from Last-Event-ID with no loss or duplicates, and the publisher on a real run.
The Redis variant runs against a real server when REDIS_URL is set (integration).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from auth_fixtures import setup_app_db, sign_in
from fastapi.testclient import TestClient

from fraudsim.api.main import app
from fraudsim.api.v1.routers import stream as stream_router
from fraudsim.api.v1.stream import hub as hub_mod
from fraudsim.api.v1.stream.hub import ALERTS, METRICS, MemoryStreams, RedisStreams


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


# ─── Hub contract ─────────────────────────────────────────────────────────────


async def check_contract(h) -> None:  # type: ignore[no-untyped-def]
    ids = [await h.publish("s:test", {"n": i}) for i in range(5)]
    assert ids == sorted(ids, key=hub_mod._id_key) and len(set(ids)) == 5
    assert [p["n"] for _, p in await h.read("s:test", "0-0", 0)] == [0, 1, 2, 3, 4]
    assert [p["n"] for _, p in await h.read("s:test", ids[2], 0)] == [3, 4]
    assert await h.read("s:test", ids[-1], 0) == []
    assert await h.last_id("s:test") == ids[-1]
    assert await h.last_id("s:empty") == "0-0"


def test_memory_hub_contract() -> None:
    run(check_contract(MemoryStreams()))


def test_redis_hub_contract_with_fakeredis() -> None:
    import fakeredis

    async def go() -> None:
        h = RedisStreams.__new__(RedisStreams)
        h._client = fakeredis.FakeAsyncRedis(decode_responses=True)
        await check_contract(h)

    run(go())


def test_memory_hub_wakes_a_blocked_reader() -> None:
    h = MemoryStreams()

    async def scenario() -> list[int]:
        reader = asyncio.create_task(h.read("s:w", "0-0", block_ms=5000))
        await asyncio.sleep(0.05)
        await h.publish("s:w", {"n": 7})
        return [p["n"] for _, p in await reader]

    t0 = time.monotonic()
    assert run(scenario()) == [7] and time.monotonic() - t0 < 2


def test_memory_hub_is_bounded() -> None:
    h = MemoryStreams()
    for i in range(hub_mod.MAXLEN[METRICS] + 10):
        run(h.publish(METRICS, {"n": i}))
    got = run(h.read(METRICS, "0-0", 0, count=10_000))
    assert len(got) == hub_mod.MAXLEN[METRICS] and got[0][1]["n"] == 10


# ─── SSE over HTTP ────────────────────────────────────────────────────────────


@pytest.fixture(params=["memory", pytest.param("redis", marks=pytest.mark.integration)])
def streams(request: pytest.FixtureRequest) -> Iterator[object]:
    if request.param == "memory":
        h: object = MemoryStreams()
    else:
        url = os.environ.get("REDIS_URL")
        if not url:
            pytest.skip("REDIS_URL is not set")
        h = RedisStreams(url)
        run(h._client.delete(ALERTS))  # type: ignore[attr-defined]
    hub_mod.reset_hub(h)  # type: ignore[arg-type]
    yield h
    hub_mod.reset_hub(None)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    users = setup_app_db(tmp_path, monkeypatch)
    # Short-lived sessions end each SSE response quickly, so a test can read it whole.
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "0.02")
    monkeypatch.setattr(stream_router, "HEARTBEAT_S", 0.3)
    c = TestClient(app, base_url="https://testserver")
    sign_in(c, *users["analyst"])
    return c


def sse(client: TestClient, url: str, **kw: object) -> str:
    """One SSE response, read whole; refreshes first, since sessions here last ~1 s."""
    assert client.post("/api/v1/auth/refresh").status_code == 200
    return client.get(url, **kw).text  # type: ignore[arg-type]


def parse(body: str) -> list[dict[str, str]]:
    events = []
    for block in body.split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line and line[0] != ":"
        )
        if "data" in fields:
            events.append(fields)
    return events


def alert(run_id: str, n: int) -> dict[str, object]:
    return {"run_id": run_id, "ring_id": f"R{n}", "kind": "alert"}


def test_sse_delivers_in_order_and_resumes_without_loss_or_duplicates(
    streams: object, client: TestClient
) -> None:
    ids = [run(streams.publish(ALERTS, alert("run_a", n))) for n in range(5)]  # type: ignore[attr-defined]
    first = parse(sse(client, "/api/v1/stream/alerts?since=0-0"))
    assert [e["id"] for e in first] == ids
    assert [json.loads(e["data"])["ring_id"] for e in first] == [f"R{n}" for n in range(5)]
    assert {e["event"] for e in first} == {"alert"}

    # "Forced disconnect" after the third event: reconnect with Last-Event-ID.
    for n in range(5, 8):
        ids.append(run(streams.publish(ALERTS, alert("run_a", n))))  # type: ignore[attr-defined]
    resumed = parse(sse(client, "/api/v1/stream/alerts", headers={"Last-Event-ID": ids[2]}))
    assert [e["id"] for e in resumed] == ids[3:]  # nothing lost, nothing repeated


def test_sse_filters_by_run_and_sends_heartbeats(streams: object, client: TestClient) -> None:
    run(streams.publish(ALERTS, alert("old_run", 1)))  # type: ignore[attr-defined]
    run(streams.publish(ALERTS, alert("run_b", 2)))  # type: ignore[attr-defined]
    assert client.post("/api/v1/auth/refresh").status_code == 200
    resp = client.get("/api/v1/stream/alerts?since=0-0&run_id=run_b")
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert [json.loads(e["data"])["ring_id"] for e in parse(resp.text)] == ["R2"]
    assert ": keep-alive" in resp.text


def test_sse_needs_a_session_and_a_valid_id(streams: object, client: TestClient) -> None:
    assert (
        TestClient(app, base_url="https://testserver").get("/api/v1/stream/alerts").status_code
        == 401
    )
    assert client.get("/api/v1/stream/alerts?since=nope").status_code == 422


# ─── Publisher on a real run ──────────────────────────────────────────────────


def test_a_run_publishes_alerts_and_kpis_equal_to_the_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRAUDSIM_RUNS_DIR", str(tmp_path / "runs"))
    users = setup_app_db(tmp_path, monkeypatch)
    h = MemoryStreams()
    hub_mod.reset_hub(h)
    try:
        with TestClient(app, base_url="https://testserver") as c:
            sign_in(c, *users["analyst"])
            assert c.get("/api/v1/runs/current/metrics").status_code in (200, 404)
            c.post("/runs/start", json={"scenario": "baseline", "seed": 7, "speed_multiplier": 0})
            run_id = c.get("/status").json()["run_id"]
            deadline = time.monotonic() + 120
            while c.get("/status").json()["status"] != "finished":
                assert time.monotonic() < deadline, "run did not finish"
                time.sleep(0.3)
            time.sleep(1.0)  # trailing KPI sample
            alerts = run(h.read(ALERTS, "0-0", 0, count=10_000))
            metrics = run(h.read(METRICS, "0-0", 0, count=10_000))
            endpoint = c.get("/api/v1/runs/current/metrics?oracle=true").json()
            c.post("/runs/stop")
    finally:
        hub_mod.reset_hub(None)
    assert alerts and all(p["run_id"] == run_id for _, p in alerts)
    assert {p["kind"] for _, p in alerts} <= {"alert", "early_warning"}
    assert all(p["ring_type"] and p["members_count"] >= 2 for _, p in alerts)
    last = metrics[-1][1]
    assert last == endpoint  # every KPI on the page traces to this run's engine
    assert last["run_id"] == run_id and last["alerts_total"] >= 1
    assert last["oracle"]["label"] == "Oracle (simulator ground truth)"
