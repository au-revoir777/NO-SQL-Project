"""
Reproducibility checks (prompt 2, P1).

1. Detection is deterministic: the same stream and method give identical results twice.
2. A recorded result row is reproduced exactly, when the locked library versions
   (requirements-lock.txt) are installed. Newer NumPy / scikit-learn / NetworkX change
   detection results on identical streams (docs/paper/refine2/02_w1.md, section 0a), so this
   test is skipped under other versions instead of failing.
"""

from __future__ import annotations

import csv
from importlib.metadata import version
from pathlib import Path

import pytest

from fraudsim.experiments.harness import make_stream, run_method
from fraudsim.experiments.suite import tuned_proposed

ROOT = Path(__file__).resolve().parents[1]
LOCKED = {"numpy": "2.2.6", "scikit-learn": "1.7.2", "networkx": "3.5"}
KEYS = ("stream_digest", "rings_flagged", "rings_detected", "false_rings", "precision", "recall", "f1")


def _run():
    from fraudsim.scoring.scorer import RingScorer

    scorer = RingScorer.load(ROOT / "models/ring_scorer_lr.joblib")
    return run_method(make_stream("baseline", 1001), tuned_proposed(), scorer, "repro")


def test_detection_is_deterministic() -> None:
    a, b = _run(), _run()
    assert {k: a[k] for k in KEYS} == {k: b[k] for k in KEYS}


@pytest.mark.skipif(
    any(version(p) != v for p, v in LOCKED.items()),
    reason="recorded results are reproducible only with the locked library versions",
)
def test_recorded_e1_row_is_reproduced() -> None:
    with open(ROOT / "results/e1_baselines/results.csv", newline="", encoding="utf-8") as f:
        rec = next(r for r in csv.DictReader(f)
                   if r["method"] == "proposed" and r["scenario"] == "baseline" and r["seed"] == "1001")
    got = _run()
    assert got["stream_digest"] == rec["stream_digest"]
    for k in ("rings_flagged", "rings_detected", "false_rings"):
        assert int(got[k]) == int(rec[k]), k
    for k in ("precision", "recall", "f1"):
        assert abs(float(got[k] or 0) - float(rec[k] or 0)) < 1e-9, k
