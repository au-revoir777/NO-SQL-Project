"""
Rerun a sample of recorded rows from the first experiments (e1_baselines, e2_ablations and the
non-latency columns of e4_scale) and compare them with the recorded values. Those rows were produced on Windows; this
checks that they reproduce on the current platform with the locked library versions
(requirements-lock.txt). Prints one line per row and a summary; exit code 1 on any mismatch.

    python scripts/check_reproduction.py [--per-method 2]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS_INT = ("rings_flagged", "rings_detected", "false_rings")
KEYS_FLOAT = ("precision", "recall", "f1")


def methods(experiment: str) -> dict:
    from fraudsim.experiments.harness import PROPOSED, Method, ablation_methods, baseline_methods
    from fraudsim.experiments.suite import _with_tuned, tuned_proposed

    if experiment == "e1_baselines":
        ms = [m for m in baseline_methods() if m.name != "proposed"]
        ms += [tuned_proposed(), Method("proposed_default", "Proposed, a-priori thresholds", dict(PROPOSED))]
    else:
        ms = _with_tuned(ablation_methods())
    return {m.name: m for m in ms}


def scale_rows(per_size: int) -> tuple[int, int]:
    """Table of scale (e4_scale): stream digest, event and batch counts and median region size
    for the two smallest sizes, both modes. Latency columns are machine-dependent and skipped."""
    from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
    from fraudsim.experiments.harness import make_stream
    from fraudsim.graph.store import InMemoryGraphStore

    with open(ROOT / "results" / "e4_scale" / "results.csv", newline="", encoding="utf-8") as f:
        rec = {(int(r["users"]), int(r["seed"]), r["mode"]): r for r in csv.DictReader(f)}
    off = {"static_cypher": {"enabled": False}, "community": {"enabled": False}}
    bad = total = 0
    for n in (1_000, 5_000):
        for seed in sorted({s for (u, s, _) in rec if u == n})[:per_size]:
            k = n / 1000
            stream = make_stream("scale_sweep", seed, {
                "simulation.num_users": n, "simulation.num_devices": int(400 * k),
                "simulation.num_cards": int(400 * k), "simulation.num_ips": int(300 * k),
                "simulation.duration_seconds": 20})
            start = stream.generator.ts(0.0)
            head = [e for e in stream.events if (e.ts - start).total_seconds() < 10]
            tail = stream.events[len(head):]
            for mode, incremental in (("incremental", True), ("full", False)):
                store = InMemoryGraphStore()
                store.apply(head)
                eng = DetectionEngine(store, build_detectors(store, off),
                                      config=EngineConfig(incremental=incremental))
                eng.run(tail)
                regions = sorted(r.region for r in eng.reports)
                got = (stream.generator.digest[:16], len(stream.events), len(eng.reports),
                       regions[len(regions) // 2])
                r = rec[(n, seed, mode)]
                want = (r["stream_digest"], int(r["events_total"]), int(r["batches"]), int(r["region_p50"]))
                ok = got == want
                total += 1
                bad += not ok
                print(f"{'OK ' if ok else 'BAD'} e4_scale {n} {seed} {mode} region {want[3]} -> {got[3]}",
                      flush=True)
    return bad, total


def main() -> int:
    from fraudsim.experiments.harness import DEFAULT_MODEL, make_stream, run_method
    from fraudsim.scoring.scorer import RingScorer

    ap = argparse.ArgumentParser()
    ap.add_argument("--per-method", type=int, default=2)
    a = ap.parse_args()
    scorer = RingScorer.load(DEFAULT_MODEL)
    bad = total = 0
    for exp in ("e1_baselines", "e2_ablations"):
        ms = methods(exp)
        with open(ROOT / "results" / exp / "results.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        seen: dict[str, int] = {}
        for rec in rows:
            name = rec["method"]
            if name not in ms or seen.get(name, 0) >= a.per_method:
                continue
            seen[name] = seen.get(name, 0) + 1
            got = run_method(make_stream(rec["scenario"], int(rec["seed"])), ms[name], scorer, "repro")
            ok = got["stream_digest"] == rec["stream_digest"]
            ok &= all(int(got[k]) == int(rec[k]) for k in KEYS_INT)
            ok &= all(abs(float(got[k] or 0) - float(rec[k] or 0)) < 1e-9 for k in KEYS_FLOAT)
            total += 1
            bad += not ok
            print(f"{'OK ' if ok else 'BAD'} {exp} {rec['scenario']} {rec['seed']} {name} "
                  f"f1 {rec['f1']} -> {got['f1']}", flush=True)
    sb, st = scale_rows(a.per_method)
    bad, total = bad + sb, total + st
    print(f"{total - bad}/{total} recorded rows reproduced exactly")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
