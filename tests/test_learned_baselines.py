"""E13/E14 helpers: paired statistics, the rule-free baseline on a small stream, node AUC."""

from __future__ import annotations

import copy

import pytest

from fraudsim.experiments.harness import make_stream, run_method
from fraudsim.experiments.learned_baselines import (
    collect_candidate_rows,
    paired,
    plain_cc_overrides,
    sweep_overrides,
    tabular_gb,
)
from fraudsim.simulator.scenario_loader import load_scenario


def test_paired_statistics_on_known_values() -> None:
    s = paired([0.9, 0.8, 0.7, 0.6], [0.5, 0.8, 0.6, 0.7])
    assert s["n"] == 4 and s["median_diff"] == pytest.approx(0.05)
    # Ranks of |d| over the non-zero differences 0.4, 0.1, -0.1: 3, 1.5, 1.5.
    assert s["rank_biserial"] == pytest.approx((3 + 1.5 - 1.5) / 6, abs=1e-3)
    assert paired([1.0, 1.0], [1.0, 1.0]) == {
        "n": 2,
        "median_diff": 0.0,
        "p": None,
        "rank_biserial": 0.0,
    }


def test_baseline_is_rule_free_and_its_candidates_are_deterministic() -> None:
    o = plain_cc_overrides()
    assert all(not o[d]["enabled"] for d in ("static_cypher", "hub_aware", "temporal_cycle"))
    assert o["community"] == {"algorithm": "wcc", "min_density": 0.0}
    a, info_a = collect_candidate_rows("baseline", 7)
    b, info_b = collect_candidate_rows("baseline", 7)
    assert info_a == info_b and info_a["rows"] > 0
    assert [(r.ring_id, r.label, r.features) for r in a] == [
        (r.ring_id, r.label, r.features) for r in b
    ]


def test_node_auc_is_reported_for_scored_and_unscored_methods() -> None:
    stream = make_stream("baseline", 7)
    from fraudsim.experiments.harness import DEFAULT_MODEL
    from fraudsim.experiments.suite import tuned_proposed
    from fraudsim.scoring.scorer import RingScorer

    row = run_method(stream, tuned_proposed(), RingScorer.load(DEFAULT_MODEL), "t")
    assert 0.5 < row["node_auc"] <= 1.0
    cc = run_method(
        stream,
        tabular_gb(0.5).__class__("plain", "plain", plain_cc_overrides(), scored=False),
        None,
        "t",
    )
    assert cc["node_auc"] is None or 0.0 <= cc["node_auc"] <= 1.0


def test_sweep_overrides_target_only_the_swept_mode() -> None:
    raw = copy.deepcopy(load_scenario("high_noise"))
    ov = sweep_overrides("decoy_edges", 4)
    assert ov["random_rings.evasion_weights"] == {"decoy_edges": 1.0}
    assert ov["simulation.evasion_params"] == {"decoy_edges": {"decoys_per_action": 4}}
    s = make_stream(raw, 1001, ov)
    assert s.raw["simulation"]["evasion_params"]["decoy_edges"]["decoys_per_action"] == 4
