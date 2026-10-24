"""
Scenario schema for the simulator page (P4).

Mirrors the YAML dialect read by `simulator.scenario_loader` and
`simulator.config.parse_simulation_config`, key for key, so a scenario edited in
the browser round-trips to the same YAML (and the same config hash). Field
constraints give field-level 422 errors; `validate_semantics` then runs the
real parser for the cross-field rules it enforces. Unknown keys are rejected
(a typo is an error, not a silently ignored setting).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fraudsim.simulator.config import HUB_KINDS, parse_simulation_config
from fraudsim.types import EvasionMode, RingType

AttributeKind = Literal["device", "card", "ip"]
# int | float keeps a YAML `90` an int (not 90.0), so a scenario round-trips to the
# same JSON and therefore the same config hash.
Num = float | int
NAME_PATTERN = r"^[a-z0-9][a-z0-9_]{0,63}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HubV1(_Strict):
    """A named benign hub (under `simulation.hub_distribution` in YAML)."""

    size: int = Field(ge=2, le=100_000)
    type: AttributeKind = "ip"
    category: str | None = None
    fill_time_s: Num | None = Field(default=None, ge=0)
    start_time_s: Num | None = Field(default=None, ge=0)

    @field_validator("category")
    @classmethod
    def _known_category(cls, v: str | None) -> str | None:
        if v is not None and v not in HUB_KINDS:
            raise ValueError(f"unknown hub category; expected one of {sorted(HUB_KINDS)}")
        return v


class HubSizeDistributionV1(_Strict):
    count: int = Field(default=0, ge=0, le=10_000)
    min_size: int = Field(default=3, ge=2)
    max_size: int = Field(default=40, ge=2, le=100_000)
    alpha: Num = Field(default=1.5, gt=0)
    categories: list[str] | None = None

    @field_validator("categories")
    @classmethod
    def _known_categories(cls, v: list[str] | None) -> list[str] | None:
        for c in v or []:
            if c not in HUB_KINDS:
                raise ValueError(f"unknown hub category {c!r}")
        return v


class DriftV1(_Strict):
    trigger_time_s: Num = Field(ge=0)
    new_hub_size: int | None = Field(default=None, ge=0)
    new_hub_kind: AttributeKind | None = None
    shift_multiplier: Num | None = Field(default=None, gt=0)


class BenignMixV1(_Strict):
    transaction: Num | None = Field(default=None, ge=0)
    ip_login: Num | None = Field(default=None, ge=0)
    device_link: Num | None = Field(default=None, ge=0)
    card_link: Num | None = Field(default=None, ge=0)


class SimulationV1(_Strict):
    duration_seconds: Num = Field(gt=0, le=86_400)
    target_event_rate: Num = Field(gt=0, le=10_000)
    num_users: int = Field(ge=2, le=1_000_000)
    num_devices: int | None = Field(default=None, ge=1)
    num_cards: int | None = Field(default=None, ge=1)
    num_ips: int | None = Field(default=None, ge=1)
    heavy_tail_alpha: Num | None = Field(default=None, gt=1)
    benign_mix: BenignMixV1 | None = None
    user_join_rate: Num | None = Field(default=None, ge=0)
    user_leave_rate: Num | None = Field(default=None, ge=0)
    amount_median: Num | None = Field(default=None, gt=0)
    amount_sigma: Num | None = Field(default=None, gt=0)
    hub_distribution: dict[str, HubV1] | None = Field(
        default=None, description="Named benign hubs (YAML key kept for compatibility)"
    )
    hub_size_distribution: HubSizeDistributionV1 | None = None
    drift: DriftV1 | None = None
    start_ts: str | None = None


class RingV1(_Strict):
    id: str = Field(min_length=1, max_length=64)
    type: RingType
    size: int = Field(default=3, ge=2, le=1_000)
    spawn_time_s: Num = Field(default=0.0, ge=0)
    evasion: EvasionMode = EvasionMode.NONE
    shared_attribute: str | None = Field(default=None, max_length=128)
    length: int | None = Field(default=None, ge=3, le=6)
    grow_interval_s: Num | None = Field(default=None, gt=0)
    initial_members: int | None = Field(default=None, ge=1)
    active_duration_s: Num | None = Field(default=None, gt=0)
    action_interval_s: Num | None = Field(default=None, gt=0)
    mutate_prob: Num | None = Field(default=None, ge=0, le=1)
    intensity: Num | None = Field(default=None, gt=0)


class RandomRingsV1(_Strict):
    rate_per_min: Num = Field(default=0.0, ge=0, le=600)
    types: list[RingType] | None = None
    size_min: int = Field(default=3, ge=2)
    size_max: int = Field(default=6, ge=2)
    evasion_weights: dict[EvasionMode, Num] | None = None
    active_duration_s: tuple[Num, Num] | None = None


class AdaptiveAttackerV1(_Strict):
    penalty: Num | None = Field(default=None, gt=0, le=1)
    respawn_delay_s: Num | None = Field(default=None, gt=0)
    max_rings: int | None = Field(default=None, ge=1, le=100)
    strategies: list[EvasionMode] | None = None


class ScenarioV1(_Strict):
    name: str = Field(pattern=NAME_PATTERN, description="lower-case letters, digits, _")
    description: str | None = Field(default=None, max_length=500)
    version: str | None = Field(default=None, max_length=20)
    simulation: SimulationV1
    rings: list[RingV1] = Field(default_factory=list, max_length=200)
    random_rings: RandomRingsV1 | None = None
    adaptive_attacker: AdaptiveAttackerV1 | None = None

    def raw(self) -> dict[str, Any]:
        """The scenario as the YAML loader would return it (only keys that were set)."""
        return self.model_dump(mode="json", exclude_unset=True)


def validate_semantics(scenario: ScenarioV1) -> list[dict[str, Any]]:
    """Cross-field rules of the real parser, as error details (empty when valid)."""
    try:
        parse_simulation_config(scenario.raw())
    except (ValueError, KeyError, TypeError) as exc:
        return [{"loc": ["body"], "msg": str(exc), "type": "value_error.scenario"}]
    return []
