"""E10: unit labelling (no double counting) and the metric primitives."""

from __future__ import annotations

import numpy as np
import pytest

from fraudsim.experiments.alert_units import ScoredEvent, label_units
from fraudsim.experiments.ring_calibration import (
    brier,
    ece,
    lift_at,
    precision_at,
    reliability,
)


def ev(rid: str, members: set[str], score: float, t: float = 0.0) -> ScoredEvent:
    return ScoredEvent(rid, t, frozenset(members), (), raw=score, shipped=score)


TRUTH = {"T1": {"a", "b", "c", "d"}, "T2": {"x", "y", "z"}}


def test_a_ring_found_twice_counts_once() -> None:
    rows = label_units(
        [
            ev("R1", {"a", "b", "c"}, 0.6),
            ev("R2", {"a", "b", "c", "d"}, 0.9),  # same true ring, higher score
            ev("R3", {"x", "y", "z"}, 0.4),
            ev("R4", {"p", "q"}, 0.95),
        ],
        TRUTH,
    )
    labels = {r["event"].ring_id: (r["label"], r["true_ring"]) for r in rows}
    assert labels == {
        "R1": ("duplicate", "T1"),
        "R2": ("tp", "T1"),
        "R3": ("tp", "T2"),
        "R4": ("fp", None),
    }


def test_label_ties_go_to_the_earliest_peak() -> None:
    rows = label_units([ev("R2", {"x", "y", "z"}, 0.5, t=9), ev("R1", {"x", "y"}, 0.5, t=1)], TRUTH)
    assert {r["event"].ring_id: r["label"] for r in rows} == {"R1": "tp", "R2": "duplicate"}


def test_jaccard_below_half_is_a_false_positive() -> None:
    (row,) = label_units([ev("R1", {"a", "p", "q"}, 0.9)], TRUTH)  # J = 1/6
    assert row["label"] == "fp"


def test_precision_and_lift_at_k() -> None:
    s = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    assert precision_at(s, y, 10) == 1.0  # top ceil(1) = 1 unit
    assert precision_at(s, y, 30) == pytest.approx(2 / 3)
    assert lift_at(s, y, 30) == pytest.approx((2 / 3) / 0.2)
    assert precision_at(s, y, 1) == 1.0  # at least one unit


def test_undefined_metrics_are_none_not_zero() -> None:
    empty = np.array([])
    assert precision_at(empty, empty, 5) is None and lift_at(empty, empty, 5) is None
    s, y = np.array([0.9, 0.1]), np.array([0, 0])
    assert precision_at(s, y, 50) == 0.0 and lift_at(s, y, 50) is None  # base rate 0


def test_brier_and_ece_on_known_values() -> None:
    s = np.array([0.05, 0.05, 0.95, 0.95])
    y = np.array([0, 0, 1, 1])
    assert brier(s, y) == pytest.approx(0.0025)
    assert ece(s, y) == pytest.approx(0.05)
    # Perfect calibration within each bin gives ECE 0.
    s2 = np.array([0.25] * 4 + [0.75] * 4)
    y2 = np.array([1, 0, 0, 0, 1, 1, 1, 0])
    assert ece(s2, y2) == pytest.approx(0.0)


def test_equal_mass_bins_split_by_rank() -> None:
    s = np.linspace(0.01, 0.99, 20)
    rows = reliability(s, np.zeros(20, dtype=int), bins=4, mode="mass")
    assert [r["n"] for r in rows] == [5, 5, 5, 5]
    assert rows[0]["mean_score"] < rows[-1]["mean_score"]
