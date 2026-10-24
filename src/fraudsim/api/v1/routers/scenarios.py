"""
/api/v1/scenarios: presets, validation, YAML export and admin save (P4).

Presets are `configs/scenarios/*.yaml`; scenarios saved by an admin go to
`configs/scenarios/custom/<name>.yaml` and are listed with `custom: true`.
Validation is two-step: the pydantic schema (field-level errors) and then the
simulator's own parser (cross-field rules), so the browser accepts exactly what
`fraudsim` accepts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel

from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.deps import DB, AdminUser, client_ip, csrf_protect, require_admin
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope
from fraudsim.api.v1.schemas.scenario import NAME_PATTERN, ScenarioV1, validate_semantics
from fraudsim.simulator.config import ATTRIBUTE_KINDS, HUB_KINDS
from fraudsim.simulator.scenario_loader import _DEFAULT_SCENARIO_DIR, list_scenarios, load_scenario
from fraudsim.types import EvasionMode, RingType, config_hash

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

CUSTOM_DIR = _DEFAULT_SCENARIO_DIR / "custom"


class ScenarioSummary(BaseModel):
    name: str
    description: str | None
    custom: bool
    duration_s: float
    users: int
    rings: int


class ScenarioCatalog(BaseModel):
    ring_types: list[str]
    evasion_modes: list[str]
    attribute_kinds: list[str]
    hub_categories: dict[str, str]


class ValidationResult(BaseModel):
    valid: bool
    config_hash: str
    events_estimate: int


def _custom_dir() -> Path:
    """SCENARIOS_CUSTOM_DIR overrides the folder (tests, deployments with a data volume)."""
    return Path(os.environ.get("SCENARIOS_CUSTOM_DIR", str(CUSTOM_DIR)))


def _summary(raw: dict[str, Any], custom: bool) -> ScenarioSummary:
    sim = raw.get("simulation") or {}
    return ScenarioSummary(
        name=str(raw.get("name")),
        description=raw.get("description"),
        custom=custom,
        duration_s=float(sim.get("duration_seconds", 0)),
        users=int(sim.get("num_users", 0)),
        rings=len(raw.get("rings") or []),
    )


def _load(name: str) -> tuple[dict[str, Any], bool]:
    if name in list_scenarios():
        return load_scenario(name), False
    if name in list_scenarios(_custom_dir()):
        return load_scenario(name, _custom_dir()), True
    raise ApiError(404, "unknown_scenario", f"Unknown scenario '{name}'")


def checked(scenario: ScenarioV1) -> ScenarioV1:
    """Raise a 422 envelope when the simulator's parser rejects the scenario."""
    errors = validate_semantics(scenario)
    if errors:
        raise ApiError(422, "validation_error", errors[0]["msg"], details=errors)
    return scenario


@router.get("", response_model=list[ScenarioSummary], operation_id="scenarios_list")
def scenarios() -> list[ScenarioSummary]:
    out = [_summary(load_scenario(n), False) for n in list_scenarios()]
    out += [_summary(load_scenario(n, _custom_dir()), True) for n in list_scenarios(_custom_dir())]
    return out


@router.get("/catalog", response_model=ScenarioCatalog, operation_id="scenarios_catalog")
def catalog() -> ScenarioCatalog:
    """Allowed values for the scenario builder's selects."""
    return ScenarioCatalog(
        ring_types=[t.value for t in RingType],
        evasion_modes=[m.value for m in EvasionMode],
        attribute_kinds=list(ATTRIBUTE_KINDS),
        hub_categories=dict(HUB_KINDS),
    )


@router.get(
    "/{name}",
    response_model=ScenarioV1,
    response_model_exclude_unset=True,
    operation_id="scenarios_get",
    responses={404: {"model": ErrorEnvelope, "description": "Unknown scenario"}},
)
def scenario(name: str) -> ScenarioV1:
    raw, _ = _load(name)
    return ScenarioV1.model_validate(raw)


@router.post(
    "/validate",
    response_model=ValidationResult,
    operation_id="scenarios_validate",
    responses={422: {"model": ErrorEnvelope, "description": "Field-level or semantic errors"}},
)
def validate(body: ScenarioV1) -> ValidationResult:
    """Validate a scenario as the simulator would; returns its config hash."""
    checked(body)
    sim = body.simulation
    return ValidationResult(
        valid=True,
        config_hash=config_hash(body.raw()),
        events_estimate=int(sim.duration_seconds * sim.target_event_rate),
    )


@router.post(
    "/yaml",
    operation_id="scenarios_yaml",
    response_class=Response,
    responses={
        200: {"content": {"application/x-yaml": {"schema": {"type": "string"}}}},
        422: {"model": ErrorEnvelope, "description": "Invalid scenario"},
    },
)
def to_yaml(body: ScenarioV1) -> Response:
    """The scenario as a YAML file loadable by `fraudsim` (same config hash)."""
    checked(body)
    text = yaml.safe_dump(body.raw(), sort_keys=False, allow_unicode=True)
    return Response(
        text,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{body.name}.yaml"'},
    )


@router.put(
    "/custom/{name}",
    response_model=ScenarioSummary,
    operation_id="scenarios_save_custom",
    dependencies=[Depends(require_admin), Depends(csrf_protect)],
    responses={
        403: {"model": ErrorEnvelope, "description": "Admin only"},
        409: {"model": ErrorEnvelope, "description": "A preset has this name"},
        422: {"model": ErrorEnvelope, "description": "Invalid scenario or name"},
    },
)
def save_custom(
    name: str, body: ScenarioV1, admin: AdminUser, request: Request, db: DB
) -> ScenarioSummary:
    """Admin: save to configs/scenarios/custom/<name>.yaml (overwrites a custom one)."""
    import re

    if not re.match(NAME_PATTERN, name) or body.name != name:
        raise ApiError(422, "validation_error", "Path name must equal the scenario name")
    if name in list_scenarios():
        raise ApiError(409, "conflict", f"'{name}' is a preset; choose another name")
    checked(body)
    d = _custom_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(
        yaml.safe_dump(body.raw(), sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    audit.record(
        "SCENARIO_SAVED",
        admin.email,
        "scenario",
        name,
        {"config_hash": config_hash(body.raw()), "ip": client_ip(request)},
        db,
    )
    return _summary(body.raw(), True)
