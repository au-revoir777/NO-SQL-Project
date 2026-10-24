"""E11: warnings are credited only through members known at the warning (no look-ahead)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fraudsim.experiments.early_warning_eval import evaluate, joined_by, qualifies
from fraudsim.simulator.ground_truth import GroundTruthLedger
from fraudsim.types import RingType

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def at(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


def upd(change: str, s: float, ring_id: str, members: set[str]) -> SimpleNamespace:
    return SimpleNamespace(change=change, ts=at(s), ring_id=ring_id, members=tuple(sorted(members)))


def ledger() -> GroundTruthLedger:
    led = GroundTruthLedger()
    led.spawn_ring("G1", RingType.SHARED_DEVICE, {"a", "b"}, at(0))
    led.grow_ring("G1", "c", at(10))
    led.grow_ring("G1", "d", at(20))
    led.activate_ring("G1", at(30))
    led.spawn_ring("G2", RingType.SHARED_CARD, {"x", "y", "z"}, at(5))
    led.activate_ring("G2", at(5))  # spawned at full size: not eligible
    return led


def test_joined_by_uses_only_the_past() -> None:
    led = ledger()
    assert joined_by(led.rings["G1"], at(9)) == {"a", "b"}
    assert joined_by(led.rings["G1"], at(20)) == {"a", "b", "c", "d"}


def test_qualifying_thresholds() -> None:
    assert qualifies({"a", "b"}, {"a", "b"})
    assert not qualifies({"a"}, {"a"})  # fewer than 2 shared members
    assert not qualifies({"a", "b", "p", "q"}, {"a", "b"})  # precision 0.5 < 0.66


def test_a_warning_is_not_credited_through_members_who_join_later() -> None:
    led = ledger()
    # At t=5 only a, b have joined: {c, d, a} shares just one known member.
    early = upd("early_warning", 5, "R1", {"a", "c", "d"})
    later = upd("early_warning", 25, "R2", {"a", "b", "c"})
    rings, warns = evaluate(led, [SimpleNamespace(updates=[early, later])], T0)
    g1 = next(r for r in rings if r["true_ring"] == "G1")
    assert g1["eligible"] and g1["first_warning_s"] == 25.0 and g1["lead_s"] == 5.0
    assert {w["ring_id"]: w["correct"] for w in warns} == {"R1": False, "R2": True}


def test_alerts_count_as_warnings_but_are_reported_separately() -> None:
    led = ledger()
    alert = upd("alert", 15, "R3", {"a", "b", "c"})
    rings, warns = evaluate(led, [SimpleNamespace(updates=[alert])], T0)
    g1 = next(r for r in rings if r["true_ring"] == "G1")
    assert g1["first_warning_kind"] == "alert" and g1["lead_s"] == 15.0
    assert g1["lead_early_warning_s"] is None
    assert warns == []  # precision is about early warnings only


def test_rings_spawned_at_full_size_are_not_eligible() -> None:
    rings, _ = evaluate(ledger(), [SimpleNamespace(updates=[])], T0)
    assert {r["true_ring"]: r["eligible"] for r in rings} == {"G1": True, "G2": False}
