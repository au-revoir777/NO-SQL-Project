"""
Live-run outputs to the streams (P3).

`StreamPublisher` is the broadcast callback of a LiveRun. It forwards every
message to the original WebSocket clients unchanged (`/ws` and the M7 dashboard
keep working) and also writes:

- `fraudsim:alerts`: each alert and early warning, with ring type, size and the
  top reason;
- `fraudsim:metrics`: a KPI sample (`kpis()`), at most every `METRICS_EVERY_S`
  with a trailing sample, so the last state of a run is always published;
- `fraudsim:events`: the newest events of each batch.

`kpis()` is also what `GET /api/v1/runs/current/metrics` returns, so the page
and the endpoint show the same numbers for the same run.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.concurrency import run_in_threadpool

from fraudsim.api.v1.cases.recorder import AlertRecorder
from fraudsim.api.v1.stream.hub import ALERTS, EVENTS, METRICS, hub
from fraudsim.metrics.evaluation import detect_ms, percentiles

METRICS_EVERY_S = 0.5
ALERT_CHANGES = ("alert", "early_warning")
MAX_MEMBERS = 50
STATUSES = ("candidate", "confirmed", "dissolved")


def run_status(live: Any) -> str:
    """
    The player's state, except "processing" while the player has finished but the
    detector is still working through queued events: only "finished" is final.
    """
    status = str(live.status)
    return "processing" if status == "finished" and not live.drained else status


def kpis(live: Any, run_id: str, oracle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Operational KPIs of a live run; ground-truth metrics only under `oracle`."""
    engine = live.engine
    rings = list(engine.tracker.rings.values())
    by_status = Counter(r.status.value for r in rings)
    alerted = [r for r in rings if r.alerted_at is not None]
    open_alerts = sum(1 for r in alerted if r.status.value != "dissolved")
    snap = live.snapshot()
    sim_s = float(snap.get("sim_time_s", 0.0))
    latency = percentiles([detect_ms(rep) for rep in engine.reports], ps=(50, 95, 99))
    sample: dict[str, Any] = {
        "run_id": run_id,
        "status": run_status(live),
        "scenario": live.scenario,
        "seed": live.seed,
        "sim_time_s": round(sim_s, 3),
        "events_total": int(snap.get("events_emitted", 0)),
        "events_per_s": round(live.player.current_rate(), 2),
        "wall_s": round(live.player.active_wall_s(), 3),
        "batches": len(engine.reports),
        "graph": engine.store.stats(),
        "rings_by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "alerts_total": len(alerted),
        "open_alerts": open_alerts,
        # Simulated time: scenarios run compressed, so this is not an operational rate.
        "alerts_per_sim_hour": round(len(alerted) / (sim_s / 3600.0), 2) if sim_s > 0 else None,
        "detect_ms": {k: latency[k] for k in ("count", "p50", "p95", "p99")},
    }
    if oracle:
        sample["oracle"] = {
            "label": "Oracle (simulator ground truth)",
            "ring_precision": oracle.get("ring", {}).get("precision"),
            "ring_recall": oracle.get("ring", {}).get("recall"),
            "ring_f1": oracle.get("ring", {}).get("f1"),
            "true_rings": oracle.get("true_rings"),
            "rings_detected": oracle.get("rings_detected"),
            "missed_rings": (oracle.get("true_rings") or 0) - (oracle.get("rings_detected") or 0)
            if oracle.get("true_rings") is not None
            else None,
        }
    return sample


def alert_payload(live: Any, run_id: str, update: dict[str, Any]) -> dict[str, Any]:
    ring = live.engine.tracker.rings.get(update["ring_id"])
    members = update.get("members", [])
    details = update.get("details") or {}
    return {
        "run_id": run_id,
        "ring_id": update["ring_id"],
        "kind": update["change"],
        "ts": update["ts"],
        "sim_time_s": round(float(live.snapshot().get("sim_time_s", 0.0)), 3),
        "risk": update.get("score"),
        "threshold": details.get("threshold"),
        "ring_type": ring.ring_type.value if ring is not None else None,
        "status": update.get("status"),
        "members_count": len(members),
        "members": members[:MAX_MEMBERS],
        "detectors": update.get("detectors", []),
        "top_reason": details.get("reason"),
    }


class StreamPublisher:
    """Broadcast callback for one LiveRun: WebSocket fan-out plus the streams."""

    def __init__(
        self,
        run_id: str,
        live_ref: Callable[[], Any],
        ws_broadcast: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.run_id = run_id
        self._live = live_ref
        self._ws = ws_broadcast
        self._last_metrics = 0.0
        self._trailing: asyncio.TimerHandle | None = None
        self.recorder = AlertRecorder(run_id)

    async def __call__(self, msg: dict[str, Any]) -> None:
        if self._ws is not None:
            await self._ws(msg)
        live = self._live()
        if live is None:
            return
        kind = msg.get("type")
        if kind == "RING_UPDATE":
            # Persist alerts for triage (P5); awaited, so one ring's updates stay in order.
            await run_in_threadpool(self.recorder.on_update, live, msg["update"])
        if kind == "RING_UPDATE" and msg["update"].get("change") in ALERT_CHANGES:
            await hub().publish(ALERTS, alert_payload(live, self.run_id, msg["update"]))
        elif kind == "BATCH":
            await hub().publish(
                EVENTS, {"run_id": self.run_id, "batch": msg["batch"], "events": msg["events"]}
            )
            await self._metrics(live)

    async def _metrics(self, live: Any) -> None:
        now = time.monotonic()
        if now - self._last_metrics >= METRICS_EVERY_S:
            await self.publish_metrics(live)
            return
        if self._trailing is None:  # publish the latest state once the window closes
            loop = asyncio.get_running_loop()
            delay = METRICS_EVERY_S - (now - self._last_metrics)
            self._trailing = loop.call_later(
                delay, lambda: loop.create_task(self._trailing_publish())
            )

    async def _trailing_publish(self) -> None:
        self._trailing = None
        live = self._live()
        if live is not None:
            await self.publish_metrics(live)

    async def publish_metrics(self, live: Any) -> None:
        self._last_metrics = time.monotonic()
        # Ground truth is evaluated fresh, so the last sample equals the endpoint.
        sample = kpis(live, self.run_id, live.metrics_summary())
        await hub().publish(METRICS, sample)
        if sample["status"] == "processing" and self._trailing is None:
            # Keep publishing until the detector has drained the queue, so the
            # final "finished" sample (the run's true end state) always goes out.
            loop = asyncio.get_running_loop()
            self._trailing = loop.call_later(
                METRICS_EVERY_S, lambda: loop.create_task(self._trailing_publish())
            )
