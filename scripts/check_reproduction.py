"""
Rerun a sample of recorded rows from the first experiments (Table III: e1_baselines; Table X:
e2_ablations) and compare them with the recorded values. Those rows were produced on Windows; this
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
    print(f"{total - bad}/{total} recorded rows reproduced exactly")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
