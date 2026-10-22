"""
E10 data collection: one labelled row per eligible tracked ring ("unit").

Definitions are fixed in docs/research/e10_protocol.md. In short: a unit is a
tracked ring that was scored while confirmed; its score is its peak shipped
(calibrated) risk while confirmed; its label uses the members at that peak
event (no look-ahead): `tp` for the best-scoring unit matching a true ring,
`duplicate` for further units matching the same true ring, `fp` otherwise.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.harness import Method, Stream, _append, make_stream
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.logging.replay import file_sha256
from fraudsim.metrics.evaluation import all_members, true_rings
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage

JACCARD = 0.5
CALIBRATION_SEEDS = (301, 302, 303)
SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")


@dataclass(frozen=True)
class ScoredEvent:
    ring_id: str
    t: float
    members: frozenset[str]
    features: tuple[float, ...]
    raw: float
    shipped: float


def peak_events(rows: list[dict[str, Any]], scorer: RingScorer) -> tuple[list[ScoredEvent], int]:
    """
    Peak confirmed scoring event per tracked ring, and the number of rings that
    were scored but never while confirmed (not eligible).
    """
    confirmed = [r for r in rows if r["status"] == "confirmed"]
    all_ids = {r["ring_id"] for r in rows}
    if not confirmed:
        return [], len(all_ids)
    x = np.asarray([r["features"] for r in confirmed], dtype=float)
    raw = scorer.raw_proba(x)
    shipped = scorer.predict(x)
    best: dict[str, ScoredEvent] = {}
    for r, p_raw, p_cal in zip(confirmed, raw, shipped, strict=True):
        ev = ScoredEvent(
            ring_id=r["ring_id"],
            t=float(r["t"]),
            members=frozenset(r["members"]),
            features=tuple(float(v) for v in r["features"]),
            raw=float(p_raw),
            shipped=float(p_cal),
        )
        cur = best.get(ev.ring_id)
        # Highest shipped score; ties go to the earliest event.
        if cur is None or ev.shipped > cur.shipped or (ev.shipped == cur.shipped and ev.t < cur.t):
            best[ev.ring_id] = ev
    return sorted(best.values(), key=lambda e: e.ring_id), len(all_ids - set(best))


def label_units(
    events: list[ScoredEvent], truth: dict[str, set[str]], threshold: float = JACCARD
) -> list[dict[str, Any]]:
    """Label each unit tp / duplicate / fp (see the module docstring)."""
    matched: dict[str, tuple[str, float]] = {}
    for ev in events:
        scored = [(jaccard(set(ev.members), m), rid) for rid, m in truth.items()]
        good = [(j, rid) for j, rid in scored if j >= threshold]
        if good:
            j, rid = max(good, key=lambda x: (x[0], x[1]))
            matched[ev.ring_id] = (rid, j)
    # Per true ring, the best-scoring unit is the true positive.
    order = sorted(events, key=lambda e: (-e.shipped, e.t, e.ring_id))
    owner: dict[str, str] = {}
    for ev in order:
        if ev.ring_id in matched:
            owner.setdefault(matched[ev.ring_id][0], ev.ring_id)
    out = []
    for ev in events:
        rid, j = matched.get(ev.ring_id, (None, None))
        label = "fp" if rid is None else ("tp" if owner[rid] == ev.ring_id else "duplicate")
        out.append({"event": ev, "label": label, "true_ring": rid, "jaccard": j})
    return out


def run_units(
    stream: Stream, method: Method, scorer: RingScorer, batch_size: int = 50
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the method on one stream; return unit rows and one run summary row."""
    store = InMemoryGraphStore()
    engine_cfg = EngineConfig(batch_size=batch_size, **({"full_interval_s": 5.0} | method.engine))
    stage = ScoringStage(scorer=scorer, record=True)
    if method.alert_threshold is not None:
        stage.policy.default_threshold = method.alert_threshold
    tracker = RingTracker(EnsembleConfig(**method.ensemble))
    engine = DetectionEngine(
        store,
        build_detectors(store, method.overrides),
        tracker=tracker,
        config=engine_cfg,
        scorer=stage,
    )
    engine.run(stream.events)
    gen = stream.generator
    start_t, end_t = gen.ts(0.0).timestamp(), gen.ts().timestamp()
    truth_rings = true_rings(gen.ledger)
    truth = {r.ring_id: all_members(r) for r in truth_rings}
    truth_type = {r.ring_id: r.ring_type.value for r in truth_rings}
    events, not_eligible = peak_events(stage.rows, scorer)
    labelled = label_units(events, truth)
    digest = gen.digest[:16]
    units = []
    for u in labelled:
        ev: ScoredEvent = u["event"]
        ring = tracker.rings[ev.ring_id]
        units.append(
            {
                "scenario": stream.scenario,
                "seed": stream.seed,
                "split": "calibration" if stream.seed in CALIBRATION_SEEDS else "test",
                "ring_id": ev.ring_id,
                "ring_type": ring.ring_type.value,
                "peak_t_s": round(ev.t - start_t, 3),
                "size_at_peak": len(ev.members),
                "raw": round(ev.raw, 8),
                "shipped": round(ev.shipped, 8),
                "label": u["label"],
                "true_ring": u["true_ring"] or "",
                "true_type": truth_type.get(u["true_ring"], "") if u["true_ring"] else "",
                "jaccard": round(u["jaccard"], 4) if u["jaccard"] is not None else "",
                "features": json.dumps(list(ev.features)),
                "stream_digest": digest,
            }
        )
    run = {
        "scenario": stream.scenario,
        "seed": stream.seed,
        "split": "calibration" if stream.seed in CALIBRATION_SEEDS else "test",
        "stream_digest": digest,
        "events": len(stream.events),
        "sim_hours": round((end_t - start_t) / 3600.0, 6),
        "true_rings": len(truth),
        "scored_rings": len(events) + not_eligible,
        "eligible_units": len(events),
        "not_eligible_units": not_eligible,
        "tp": sum(1 for u in units if u["label"] == "tp"),
        "duplicate": sum(1 for u in units if u["label"] == "duplicate"),
        "fp": sum(1 for u in units if u["label"] == "fp"),
        "alert_threshold": method.alert_threshold,
    }
    return units, run


def run_e10(
    out: Path,
    test_seeds: list[int],
    log: Callable[[str], None] = print,
    scenarios: tuple[str, ...] = SCENARIOS,
    calibration_seeds: tuple[int, ...] = CALIBRATION_SEEDS,
    model_path: Path | None = None,
    scenario_overrides: dict[str, Any] | None = None,
) -> Path:
    """Collect E10 units for every (scenario, seed); see docs/research/e10_protocol.md."""
    from fraudsim.experiments.harness import DEFAULT_MODEL
    from fraudsim.experiments.suite import tuned_proposed

    model_path = Path(model_path or DEFAULT_MODEL)
    scorer = RingScorer.load(model_path)
    method = tuned_proposed()
    out_dir = Path(out) / "e10_ring_alerts"
    seeds = list(calibration_seeds) + list(test_seeds)
    details = {
        "protocol": "docs/research/e10_protocol.md",
        "method": method.config() | {"label": method.label},
        "scenarios": list(scenarios),
        "calibration_seeds": list(calibration_seeds),
        "test_seeds": list(test_seeds),
        "scenario_overrides": scenario_overrides or {},
        "model": {"path": repo_relative(model_path), "sha256": file_sha256(model_path)},
    }
    with recorded(out_dir, "e10_ring_alerts", details):
        for scenario in scenarios:
            for seed in seeds:
                stream = make_stream(scenario, seed, scenario_overrides)
                units, run = run_units(stream, method, scorer)
                for u in units:
                    _append(out_dir / "units.csv", u)
                _append(out_dir / "results.csv", run)
                log(
                    f"[e10] {scenario} seed={seed} units={run['eligible_units']} "
                    f"tp={run['tp']} dup={run['duplicate']} fp={run['fp']}"
                )
    return out_dir
