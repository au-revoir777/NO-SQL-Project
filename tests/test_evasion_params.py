"""simulation.evasion_params: per-mode overrides of the evasion strategies (P12, E14)."""

from __future__ import annotations

import copy

import pytest

from fraudsim.simulator.config import parse_simulation_config
from fraudsim.simulator.event_generator import EventGenerator
from fraudsim.simulator.rings import STRATEGIES, strategy_params
from fraudsim.simulator.scenario_loader import load_scenario
from fraudsim.types import EvasionMode, EventType


def _cfg(params: dict | None) -> dict:
    raw = copy.deepcopy(load_scenario("high_noise"))
    raw["random_rings"]["evasion_weights"] = {"decoy_edges": 1.0}
    if params is not None:
        raw["simulation"]["evasion_params"] = params
    return raw


def test_parsing_validates_modes_keys_and_values() -> None:
    cfg = parse_simulation_config(_cfg({"decoy_edges": {"decoys_per_action": 4}}))
    assert cfg.evasion_params == {"decoy_edges": {"decoys_per_action": 4}}
    with pytest.raises(ValueError):
        parse_simulation_config(_cfg({"teleport": {"decoys_per_action": 1}}))
    with pytest.raises(ValueError, match="not a strategy parameter"):
        parse_simulation_config(_cfg({"decoy_edges": {"decoys": 1}}))
    with pytest.raises(ValueError, match="must be positive"):
        parse_simulation_config(_cfg({"low_and_slow": {"action_mult": 0}}))
    assert parse_simulation_config(_cfg(None)).evasion_params == {}


def test_overrides_apply_only_to_their_mode() -> None:
    cfg = parse_simulation_config(_cfg({"identity_rotation": {"rotate_every": 1}}))
    assert strategy_params(EvasionMode.IDENTITY_ROTATION, cfg).rotate_every == 1
    assert strategy_params(EvasionMode.DECOY_EDGES, cfg) == STRATEGIES[EvasionMode.DECOY_EDGES]
    assert strategy_params(EvasionMode.NONE, None) == STRATEGIES[EvasionMode.NONE]


def _transactions(raw: dict, seed: int = 1001) -> tuple[int, str]:
    gen = EventGenerator(seed=seed, run_id="t", config=raw)
    events = gen.generate()
    return sum(e.event_type == EventType.TRANSACTION for e in events), gen.digest


def test_absent_or_default_overrides_leave_the_stream_unchanged() -> None:
    plain = _transactions(_cfg(None))
    assert _transactions(_cfg({})) == plain
    # The mode's own default value as an explicit override: same stream.
    assert _transactions(_cfg({"decoy_edges": {"decoys_per_action": 2}})) == plain
    # A shipped scenario without the field keeps its digest.
    raw = load_scenario("baseline")
    assert _transactions(raw)[1] == _transactions(copy.deepcopy(raw))[1]


def _decoy_transfers(k: int, seed: int = 1001) -> int:
    """Transfers from ring members to accounts in no ring (what decoys add)."""
    gen = EventGenerator(
        seed=seed, run_id="t", config=_cfg({"decoy_edges": {"decoys_per_action": k}})
    )
    events = gen.generate()
    in_ring = {u for r in gen.ledger.rings.values() for _, a, u in r.member_history if a == "join"}
    return sum(
        e.event_type == EventType.TRANSACTION
        and e.payload["sender"] in in_ring
        and e.payload["receiver"] not in in_ring
        for e in events
    )


def test_more_decoys_mean_more_decoy_transfers() -> None:
    counts = [_decoy_transfers(k) for k in (0, 2, 8)]
    assert counts[0] < counts[1] < counts[2]
