"""E12 metric primitives on hand-made inputs with known answers (docs/research/e12_protocol.md)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fraudsim.experiments.explanation_quality import (
    NON_ACTIONABLE,
    check_counterfactual,
    contribution_drift,
    contribution_vector,
    fidelity,
    jaccard_sets,
    perturb,
    same_first,
    spearman,
    top_features,
    unit_rng,
)
from fraudsim.scoring.explanations import model_counterfactuals
from fraudsim.scoring.features import FEATURE_NAMES
from fraudsim.scoring.scorer import RingScorer

N = len(FEATURE_NAMES)
I_SIZE = FEATURE_NAMES.index("size")  # actionable


@pytest.fixture(scope="module")
def lr() -> RingScorer:
    """A logistic regression whose label depends on `size` only (other features noise)."""
    rng = np.random.default_rng(0)
    x = rng.normal(0.0, 1.0, size=(4000, N))
    x[:, I_SIZE] = rng.uniform(0.0, 20.0, size=4000)
    y = (x[:, I_SIZE] + rng.normal(0, 1.0, 4000) > 10.0).astype(int)
    return RingScorer("logistic_regression").fit(x[:3000], y[:3000], x[3000:], y[3000:])


def test_counterfactual_is_the_closed_form_and_flips_the_decision(lr: RingScorer) -> None:
    x = np.zeros(N)
    x[I_SIZE] = 18.0
    assert float(lr.predict(x)[0]) >= 0.8
    target = lr.counterfactual_value(x, "size", 0.8)
    assert target is not None and 0 < target < 18.0
    # Closed form: the raw log-odds at the target equal logit(raw threshold) - 1e-3.
    raw_t = lr.raw_threshold_for(0.8)
    assert raw_t is not None
    y = x.copy()
    y[I_SIZE] = target
    p = float(lr.raw_proba(y)[0])
    assert math.log(p / (1 - p)) == pytest.approx(math.log(raw_t / (1 - raw_t)) - 1e-3, abs=1e-6)
    valid, new = check_counterfactual(lr, x, "size", target)
    assert valid and new < 0.8
    # The product's counterfactual list proposes exactly this change first.
    cfs = model_counterfactuals(lr, x, lr.contributions(x), 0.8)
    assert cfs[0][0] == "size" and cfs[0][2] == pytest.approx(target)
    # The pre-E12 computation aimed at the isotonic breakpoint and did not flip it
    # (protocol amendment 1): the calibrated score stayed above the threshold.
    legacy = lr.counterfactual_value(x, "size", 0.8, exact_crossing=False)
    assert legacy is not None and legacy > target
    assert not check_counterfactual(lr, x, "size", legacy)[0]
    # Moving less than the counterfactual does not flip it.
    assert not check_counterfactual(lr, x, "size", (target + 18.0) / 2)[0]


def test_zero_perturbation_is_perfectly_stable(lr: RingScorer) -> None:
    x = np.zeros(N)
    x[I_SIZE] = 15.0
    xp = perturb(x, 0.0, unit_rng("s", 1, "R1", 0.0))
    assert np.array_equal(xp, x)
    c0, c1 = lr.contributions(x), lr.contributions(xp)
    assert contribution_drift(contribution_vector(c0), contribution_vector(c1)) == 0.0
    assert jaccard_sets(top_features(c0), top_features(c1)) == 1.0
    first = model_counterfactuals(lr, x, c0, 0.8)
    assert same_first(first[0] if first else None, model_counterfactuals(lr, xp, c1, 0.8))


def test_perturbation_touches_only_non_actionable_features() -> None:
    x = np.arange(1.0, N + 1.0)
    xp = perturb(x, 0.05, unit_rng("s", 1, "R1", 0.05))
    for i, f in enumerate(FEATURE_NAMES):
        if f in NON_ACTIONABLE:
            assert abs(xp[i] / x[i] - 1.0) <= 0.05
        else:
            assert xp[i] == x[i]
    # Seeded per unit: the same draw every time.
    assert np.array_equal(xp, perturb(x, 0.05, unit_rng("s", 1, "R1", 0.05)))


def test_metric_primitives_on_known_values() -> None:
    assert contribution_drift(np.array([1.0, -1.0]), np.array([1.5, -0.5])) == 0.5
    assert contribution_drift(np.zeros(2), np.zeros(2)) == 0.0
    contrib = {f: 0.0 for f in FEATURE_NAMES}
    contrib.update({"size": 3.0, "density": -2.0, "share_ip": 1.0, "amount_cv": 0.5})
    assert top_features(contrib) == {"size", "density", "share_ip"}
    assert jaccard_sets({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert fidelity({"u1", "u2", "u3", "u4"}, {"u1", "u2", "u9"}) == (0.5, 2 / 3)
    assert spearman(np.array([1.0, 2.0, 3.0]), np.array([10.0, 20.0, 30.0])) == pytest.approx(1.0)
    assert spearman(np.ones(3), np.array([1.0, 2.0, 3.0])) is None
    assert same_first(None, []) and not same_first(None, [("size", 1.0, 0.5)])
    assert same_first(("size", 2.0, 1.0), [("size", 2.1, 1.1)])
