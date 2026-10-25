"""
E8: latency on the real stack (Redis Streams -> detection engine -> Neo4j), as
fixed in docs/research/e8_protocol.md.

    python -m fraudsim.experiments.stack_latency --run --results-dir results \
        --neo4j-uri bolt://localhost:17687 --redis-url redis://localhost:16379/0
    python -m fraudsim.experiments.stack_latency --report docs/research/e8_tables.md

NEO4J_PASSWORD must be set (the experiment wipes that database). The metric
helpers are unit-tested; the runs need the services.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import subprocess
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from fraudsim.detectors.engine import BatchReport, DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.harness import DEFAULT_MODEL, Method, Stream, _append, make_stream
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.graph.neo4j_client import Neo4jClient
from fraudsim.graph.neo4j_store import Neo4jGraphStore
from fraudsim.graph.store import GraphStore, InMemoryGraphStore
from fraudsim.logging.replay import file_sha256
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage
from fraudsim.stream.event_bus import RedisStreamBus
from fraudsim.types import Event, config_hash

EXPERIMENT = "e8_stack_latency"
BATCH = 50
FLAG_CHANGES = ("confirmed", "alert", "early_warning")
E1_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
SEEDS = (1001, 1002, 1003)
SIZES = (1_000, 5_000, 20_000)
COUNTS = (10, 100, 500)
BLOCKS = (5, 50, 500)


# ─── Metric helpers (tests/test_stack_latency.py) ─────────────────────────────


def pct(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile on the sorted values (None when empty)."""
    if not values:
        return None
    s = sorted(values)
    rank = max(1, math.ceil(p / 100.0 * len(s)))
    return s[min(rank, len(s)) - 1]


def summary(values: Sequence[float], prefix: str) -> dict[str, float | None]:
    return {
        f"{prefix}_p50": _r(pct(values, 50)),
        f"{prefix}_p95": _r(pct(values, 95)),
        f"{prefix}_p99": _r(pct(values, 99)),
        f"{prefix}_n": len(values),
    }


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 3)


def detect_ms(report: BatchReport) -> float:
    """Detection time of one batch, as E4 defines it (dirty region + view + detectors)."""
    return (
        report.timings_ms.get("dirty", 0.0)
        + report.timings_ms.get("view", 0.0)
        + sum(report.detector_ms.values())
    )


def update_signature(reports: Sequence[BatchReport]) -> list[tuple[str, str, tuple[str, ...]]]:
    """Every ring update in order: (ring id, change, sorted members)."""
    return [(u.ring_id, u.change, tuple(sorted(u.members))) for r in reports for u in r.updates]


def flagged(reports: Sequence[BatchReport]) -> set[tuple[str, tuple[str, ...]]]:
    """Rings confirmed or alerted, with their members at that update."""
    return {
        (u.ring_id, tuple(sorted(u.members)))
        for r in reports
        for u in r.updates
        if u.change in ("confirmed", "alert")
    }


def schedule(events: Sequence[Event], speed: float) -> list[float]:
    """Wall offsets (s) at which a paced producer publishes each event."""
    t0 = events[0].ts.timestamp() if events else 0.0
    return [(e.ts.timestamp() - t0) / speed for e in events]


# ─── Engine (as E1/E10's run_scored, on any store) ────────────────────────────


def build_engine(store: GraphStore, method: Method, scorer: RingScorer) -> DetectionEngine:
    stage = ScoringStage(scorer=scorer, record=False)
    if method.alert_threshold is not None:
        stage.policy.default_threshold = method.alert_threshold
    return DetectionEngine(
        store,
        build_detectors(store, method.overrides),
        tracker=RingTracker(EnsembleConfig(**method.ensemble)),
        config=EngineConfig(batch_size=BATCH, **({"full_interval_s": 5.0} | method.engine)),
        scorer=stage,
    )


@dataclass
class Stack:
    neo4j_uri: str
    neo4j_password: str
    redis_url: str


@dataclass
class RunResult:
    reports: list[BatchReport]
    batches: list[dict[str, Any]]
    row: dict[str, Any]


async def run_stack(
    stream: Stream,
    events: Sequence[Event],
    method: Method,
    scorer: RingScorer,
    stack: Stack,
    *,
    speed: float | None,
    count: int,
    block_ms: int,
    bootstrap: Sequence[Event] = (),
) -> RunResult:
    """One run through Redis Streams and Neo4j; timestamps as in the protocol."""
    client = Neo4jClient(uri=stack.neo4j_uri, password=stack.neo4j_password)
    try:
        client.wipe()
        client.ensure_schema()
        store = Neo4jGraphStore(client)
        if bootstrap:
            store.apply(list(bootstrap))
        engine = build_engine(store, method, scorer)
        bus = RedisStreamBus(
            redis_url=stack.redis_url,
            stream_name=f"e8:{uuid.uuid4().hex}",
            maxlen=None,
            block_ms=block_ms,
            count=count,
        )
        published: dict[int, float] = {}
        read: dict[int, float] = {}
        offsets = schedule(events, speed) if speed else None
        subscription = await bus.subscribe()

        async def produce() -> None:
            t0 = time.perf_counter()
            i = 0
            while i < len(events):
                if offsets is None:
                    chunk = list(events[i : i + 100])
                else:
                    wait = t0 + offsets[i] - time.perf_counter()
                    if wait > 0:
                        await asyncio.sleep(wait)
                    now = time.perf_counter() - t0
                    j = i
                    while j < len(events) and offsets[j] <= now:
                        j += 1
                    chunk = list(events[i : max(j, i + 1)])
                await bus.publish_batch(chunk)
                t = time.perf_counter()
                for e in chunk:
                    published[e.seq] = t
                i += len(chunk)
            await bus.close()

        batches: list[dict[str, Any]] = []
        reports: list[BatchReport] = []

        async def consume() -> None:
            batch: list[Event] = []

            async def flush() -> None:
                lag_events = len(published) - len(read)
                start = time.perf_counter()
                report = await asyncio.to_thread(engine.process, batch)
                end = time.perf_counter()
                reports.append(report)
                write_end = start + report.timings_ms.get("ingest", 0.0) / 1000.0
                first, last = batch[0], batch[-1]
                batches.append(
                    {
                        "batch": report.batch,
                        "events": len(batch),
                        "ingest_to_write_ms": [
                            round((write_end - published[e.seq]) * 1000, 3) for e in batch
                        ],
                        "detect_ms": round(detect_ms(report), 3),
                        "batch_total_ms": round((end - start) * 1000, 3),
                        "flags": [u.change for u in report.updates if u.change in FLAG_CHANGES],
                        "event_to_flag_ms": round((end - published[last.seq]) * 1000, 3),
                        "lag_events": lag_events,
                        "lag_ms": round((read[first.seq] - published[first.seq]) * 1000, 3),
                        "end": end,
                    }
                )

            async for e in subscription:
                read[e.seq] = time.perf_counter()
                batch.append(e)
                if len(batch) >= BATCH:
                    await flush()
                    batch = []
            if batch:
                await flush()

        t_start = time.perf_counter()
        await asyncio.gather(produce(), consume())
        first_pub = min(published.values()) if published else t_start
        last_end = batches[-1]["end"] if batches else t_start
    finally:
        client.close()
    flags = [b["event_to_flag_ms"] for b in batches for _ in b["flags"]]
    row: dict[str, Any] = {
        "events": len(events),
        "batches": len(batches),
        "flags": len(flags),
        **summary([v for b in batches for v in b["ingest_to_write_ms"]], "ingest_to_write_ms"),
        **summary([b["detect_ms"] for b in batches], "detect_ms"),
        **summary([b["batch_total_ms"] for b in batches], "batch_total_ms"),
        **summary(flags, "event_to_flag_ms"),
        **summary([b["lag_ms"] for b in batches], "lag_ms"),
        "lag_events_max": max((b["lag_events"] for b in batches), default=0),
        "events_per_s": round(len(events) / (last_end - first_pub), 1)
        if last_end > first_pub
        else None,
    }
    for b in batches:
        b.pop("end")
    return RunResult(reports, batches, row)


def check_against_memory(
    events: Sequence[Event],
    bootstrap: Sequence[Event],
    method: Method,
    scorer: RingScorer,
    stack_reports: Sequence[BatchReport],
) -> dict[str, Any]:
    store = InMemoryGraphStore()
    if bootstrap:
        store.apply(list(bootstrap))
    engine = build_engine(store, method, scorer)
    mem = engine.run(events)
    same_updates = update_signature(mem) == update_signature(stack_reports)
    same_flags = flagged(mem) == flagged(stack_reports)
    return {
        "same_updates": same_updates,
        "same_flagged": same_flags,
        "memory_updates": len(update_signature(mem)),
        "stack_updates": len(update_signature(stack_reports)),
        "flagged_rings": len(flagged(mem)),
        "memory_detect_ms_p50": _r(pct([detect_ms(r) for r in mem], 50)),
        "memory_detect_ms_p95": _r(pct([detect_ms(r) for r in mem], 95)),
    }


# ─── Runs ─────────────────────────────────────────────────────────────


def _docker(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=20, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def environment_note() -> dict[str, Any]:
    return {
        "host": platform.platform(),
        "cpu_count": os.cpu_count(),
        "docker_server": _docker("version", "--format", "{{.Server.Version}}"),
        "containers_running": (
            _docker("ps", "--format", "{{.Names}} {{.Image}}") or ""
        ).splitlines(),
    }


def run_all(
    out: Path,
    stack: Stack,
    log: Callable[[str], None] = print,
    scenarios: Sequence[str] = E1_SCENARIOS,
    seeds: Sequence[int] = SEEDS,
    sizes: Sequence[int] = SIZES,
    counts: Sequence[int] = COUNTS,
    blocks: Sequence[int] = BLOCKS,
    parts: Sequence[str] = ("warmup", "e1", "users", "read"),
) -> Path:
    from fraudsim.experiments.suite import tuned_proposed

    method = tuned_proposed()
    scorer = RingScorer.load(DEFAULT_MODEL)
    out_dir = Path(out) / EXPERIMENT
    details = {
        "protocol": "docs/research/e8_protocol.md",
        "method": method.config() | {"label": method.label},
        "model": {"path": repo_relative(DEFAULT_MODEL), "sha256": file_sha256(DEFAULT_MODEL)},
        "batch_size": BATCH,
        "environment": environment_note(),
        "neo4j_image": "neo4j:5.26-community",
        "redis_image": "redis:7.4-alpine",
        "parts": list(parts),
    }

    def one(
        phase: str,
        scenario: str,
        seed: int,
        overrides: dict[str, Any] | None,
        speed: float | None,
        count: int,
        block_ms: int,
        bootstrap_s: float | None = None,
        users: int | None = None,
    ) -> None:
        stream = make_stream(scenario, seed, overrides)
        evs = stream.events
        boot: list[Event] = []
        if bootstrap_s is not None:
            start = stream.generator.ts(0.0)
            boot = [e for e in evs if (e.ts - start).total_seconds() < bootstrap_s]
            evs = evs[len(boot) :]
        res = asyncio.run(
            run_stack(
                stream,
                evs,
                method,
                scorer,
                stack,
                speed=speed,
                count=count,
                block_ms=block_ms,
                bootstrap=boot,
            )
        )
        check = check_against_memory(evs, boot, method, scorer, res.reports)
        run_id = f"e8:{phase}:{scenario}:{users or ''}:{seed}:{count}:{block_ms}:{speed or 'max'}"
        row = {
            "experiment": EXPERIMENT,
            "run_id": run_id,
            "phase": phase,
            "scenario": scenario,
            "users": users or "",
            "seed": seed,
            "config_hash": config_hash(stream.raw),
            "stream_digest": stream.generator.digest[:16],
            "paced_speed": speed or "",
            "xread_count": count,
            "xread_block_ms": block_ms,
            "bootstrap_events": len(boot),
            **res.row,
            **check,
        }
        _append(out_dir / "results.csv", row)
        for b in res.batches:
            _append(
                out_dir / "per_batch.csv",
                {
                    "run_id": run_id,
                    **{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in b.items()},
                },
            )
        log(
            f"[e8] {phase} {scenario} users={users or '-'} seed={seed} c={count} b={block_ms} "
            f"flag_p50={row['event_to_flag_ms_p50']} ev/s={row['events_per_s']} "
            f"same={check['same_updates']}"
        )

    with recorded(out_dir, EXPERIMENT, details):
        if "warmup" in parts:
            one("warmup", "baseline", 999, None, None, 100, 50)
        if "e1" in parts:
            for sc in scenarios:
                for seed in seeds:
                    one("e1_paced", sc, seed, None, 1.0, 100, 50)
        if "users" in parts:
            for n in sizes:
                f = n / 1000
                ov = {
                    "simulation.num_users": n,
                    "simulation.num_devices": int(400 * f),
                    "simulation.num_cards": int(400 * f),
                    "simulation.num_ips": int(300 * f),
                    "simulation.duration_seconds": 20,
                }
                for seed in seeds:
                    one("users_unpaced", "scale_sweep", seed, ov, None, 100, 50, 10.0, n)
        if "read" in parts:
            for c in counts:
                for b in blocks:
                    for seed in seeds:
                        one("read_sweep", "baseline", seed, None, 1.0, c, b)
    return out_dir


# ─── Report ───────────────────────────────────────────────────────────


def report(results_dir: Path, out: Path) -> Path:
    df = pd.read_csv(Path(results_dir) / EXPERIMENT / "results.csv")
    lines = [
        "# E8 tables (generated)",
        "",
        "Generated by `python -m fraudsim.experiments.stack_latency --report "
        "docs/research/e8_tables.md` from `results/e8_stack_latency/results.csv`. "
        "Do not edit by hand. Milliseconds; each cell is the median over seeds of the "
        "per-run percentile.",
        "",
        "## Correctness: identical to the in-memory engine on the same events",
        "",
        f"Runs: {len(df)}; identical update sequence: {int(df['same_updates'].sum())}; "
        f"identical flagged rings: {int(df['same_flagged'].sum())}.",
        "",
    ]

    def block(title: str, g: pd.DataFrame, by: list[str]) -> None:
        lines.extend(
            [
                f"## {title}",
                "",
                "| " + " | ".join(by) + " | Runs | Ingest→write p50 / p95 | Detect p50 / p95 "
                "(in-memory p50) | Event→flag p50 / p95 / p99 | Lag p95 | Max lag (events) | "
                "Events/s |",
                "|" + "---|" * (len(by) + 7),
            ]
        )
        for key, h in g.groupby(by, sort=True):
            keys = key if isinstance(key, tuple) else (key,)
            m = h.median(numeric_only=True)
            lines.append(
                "| "
                + " | ".join(str(k) for k in keys)
                + f" | {len(h)} | {m['ingest_to_write_ms_p50']:.1f}"
                f" / {m['ingest_to_write_ms_p95']:.1f}"
                f" | {m['detect_ms_p50']:.1f} / {m['detect_ms_p95']:.1f} "
                f"({m['memory_detect_ms_p50']:.1f})"
                f" | {m['event_to_flag_ms_p50']:.1f} / {m['event_to_flag_ms_p95']:.1f} / "
                f"{m['event_to_flag_ms_p99']:.1f} | {m['lag_ms_p95']:.1f} | "
                f"{m['lag_events_max']:.0f} | {m['events_per_s']:.0f} |"
            )
        lines.append("")

    warm = df[df["phase"] == "warmup"]
    if len(warm):
        block("JVM warm-up run (excluded from everything below)", warm, ["scenario"])
    for phase, title, by in (
        (
            "e1_paced",
            "Shortened E1, paced at simulated speed 1 (XREAD COUNT 100 BLOCK 50)",
            ["scenario"],
        ),
        (
            "users_unpaced",
            "Users sweep, unpaced (scale_sweep, after the 10 s bootstrap)",
            ["users"],
        ),
        (
            "read_sweep",
            "Redis read sweep, baseline, paced at speed 1",
            ["xread_count", "xread_block_ms"],
        ),
    ):
        g = df[df["phase"] == phase]
        if len(g):
            block(title, g, by)
    Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return Path(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    p.add_argument("--run", action="store_true")
    p.add_argument("--parts", default="warmup,e1,users,read")
    p.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    p.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    if args.run:
        password = os.environ.get("NEO4J_PASSWORD", "")
        if not password:
            p.error("set NEO4J_PASSWORD (this experiment wipes that database)")
        run_all(
            args.results_dir,
            Stack(args.neo4j_uri, password, args.redis_url),
            parts=tuple(args.parts.split(",")),
        )
    if args.report:
        report(args.results_dir, args.report)


if __name__ == "__main__":
    main()
