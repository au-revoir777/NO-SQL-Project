"""/api/v1/runs: start a live run, and read the current run and its KPIs from the engine."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from fraudsim.api.state import state
from fraudsim.api.v1.auth.deps import require_admin
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope, RunStatusV1
from fraudsim.api.v1.schemas.scenario import ScenarioV1
from fraudsim.api.v1.schemas.stream import RunMetricsV1
from fraudsim.api.v1.stream.publisher import kpis, run_status
from fraudsim.types import EvasionMode, RingType, config_hash

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunV1(BaseModel):
    scenario: str = Field(
        "baseline", max_length=64, description="Preset name (ignored with config)"
    )
    config: ScenarioV1 | None = Field(
        default=None, description="An inline scenario from the builder (validated like a preset)"
    )
    seed: int = Field(42, ge=0, le=2**31 - 1)
    speed_multiplier: float = Field(1.0, ge=0.0, le=1000.0, description="0 = as fast as possible")


class SpeedV1(BaseModel):
    speed_multiplier: float = Field(ge=0.0, le=1000.0, description="0 = as fast as possible")


class RateV1(BaseModel):
    events_per_second: float = Field(gt=0.0, le=10_000.0)


class InjectV1(BaseModel):
    ring_type: RingType
    evasion: EvasionMode = EvasionMode.NONE
    size: int = Field(4, ge=2, le=50)


class InjectedV1(BaseModel):
    ring_id: str
    sim_time_s: float


class DetectorV1(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str
    enabled: bool


class DetectorToggleV1(BaseModel):
    enabled: bool


class GraphSnapshotV1(BaseModel):
    """Windowed live graph (nodes and edges as built for the dashboards)."""

    model_config = ConfigDict(extra="allow")
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    shown_users: int
    total_active_users: int


NO_RUN: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorEnvelope, "description": "No run in progress"}
}


def _live() -> Any:
    if state.live is None:
        raise ApiError(409, "no_run", "No run in progress")
    return state.live


@router.get("/current", response_model=RunStatusV1, operation_id="runs_current")
async def current_run() -> RunStatusV1:
    live = state.live
    snap = live.snapshot() if live is not None else {}
    return RunStatusV1(
        run_id=state.run_id,
        status=run_status(live) if live is not None else state.status,
        scenario=state.scenario,
        seed=state.seed,
        events_emitted=int(snap.get("events_emitted", state.events_emitted)),
        rings_tracked=len(live.engine.tracker.live()) if live is not None else 0,
        sim_time_s=float(snap.get("sim_time_s", 0.0)),
        speed_multiplier=float(snap.get("speed_multiplier", state.speed_multiplier)),
        scenario_hash=config_hash(live.scenario_config) if live is not None else None,
        stream_digest=live.generator.digest if live is not None else None,
    )


@router.get(
    "/current/metrics",
    response_model=RunMetricsV1,
    operation_id="runs_current_metrics",
    responses={404: {"model": ErrorEnvelope, "description": "No run has been started"}},
)
def current_run_metrics(oracle: bool = False) -> RunMetricsV1:
    """
    The same KPI sample the dashboard receives over SSE. `oracle=true` adds the
    simulator ground-truth metrics (labelled as such).
    """
    live = state.live
    if live is None:
        raise ApiError(404, "no_run", "No run has been started")
    return RunMetricsV1.model_validate(
        kpis(live, state.run_id, live.metrics_summary() if oracle else None)
    )


@router.post(
    "",
    response_model=RunStatusV1,
    status_code=201,
    operation_id="runs_start",
    responses={
        404: {"model": ErrorEnvelope, "description": "Unknown scenario"},
        422: {"model": ErrorEnvelope, "description": "Invalid inline scenario"},
    },
)
async def start_run(body: StartRunV1) -> RunStatusV1:
    """Stop the current run, if any, and start a new one (simulator in memory)."""
    from fraudsim.api.run_control import UnknownScenarioError, start_live_run
    from fraudsim.api.v1.routers.scenarios import checked

    config = checked(body.config).raw() if body.config is not None else None
    name = body.config.name if body.config is not None else body.scenario
    try:
        await start_live_run(name, body.seed, body.speed_multiplier, config=config)
    except UnknownScenarioError:
        raise ApiError(404, "unknown_scenario", f"Unknown scenario '{body.scenario}'") from None
    return await current_run()


async def _broadcast(msg: dict[str, Any]) -> None:
    await state.broadcast_ws(msg)  # the M7 dashboard keeps seeing control changes


@router.post(
    "/current/pause", response_model=RunStatusV1, operation_id="runs_pause", responses=NO_RUN
)
async def pause() -> RunStatusV1:
    live = _live()
    if live.status == "running":
        live.pause()
        await _broadcast({"type": "RUN_PAUSED", "run_id": state.run_id})
    return await current_run()


@router.post(
    "/current/resume", response_model=RunStatusV1, operation_id="runs_resume", responses=NO_RUN
)
async def resume() -> RunStatusV1:
    live = _live()
    if live.status == "paused":
        live.resume()
        await _broadcast({"type": "RUN_RESUMED", "run_id": state.run_id})
    return await current_run()


@router.post(
    "/current/stop", response_model=RunStatusV1, operation_id="runs_stop", responses=NO_RUN
)
async def stop() -> RunStatusV1:
    from fraudsim.api.run_control import run_lock

    async with run_lock:
        live = _live()
        await live.stop()
        state.events_emitted = live.events_consumed
    await _broadcast({"type": "RUN_STOPPED", "run_id": state.run_id})
    return await current_run()


@router.post(
    "/current/speed", response_model=RunStatusV1, operation_id="runs_speed", responses=NO_RUN
)
async def speed(body: SpeedV1) -> RunStatusV1:
    _live().set_speed(body.speed_multiplier)
    state.speed_multiplier = body.speed_multiplier
    await _broadcast({"type": "RUN_SPEED", "speed_multiplier": body.speed_multiplier})
    return await current_run()


@router.post(
    "/current/rate", response_model=RunStatusV1, operation_id="runs_rate", responses=NO_RUN
)
async def rate(body: RateV1) -> RunStatusV1:
    _live().set_rate(body.events_per_second)
    await _broadcast({"type": "RUN_RATE", "events_per_second": body.events_per_second})
    return await current_run()


@router.post(
    "/current/inject",
    response_model=InjectedV1,
    status_code=201,
    operation_id="runs_inject",
    responses=NO_RUN,
)
async def inject(body: InjectV1) -> InjectedV1:
    """Spawn a fraud ring of the given type and evasion right now."""
    live = _live()
    try:
        ring_id = live.inject(body.ring_type.value, body.evasion.value, body.size)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc
    await _broadcast(
        {
            "type": "RING_INJECTED",
            "ring_id": ring_id,
            "ring_type": body.ring_type.value,
            "evasion": body.evasion.value,
            "size": body.size,
        }
    )
    return InjectedV1(ring_id=ring_id, sim_time_s=float(live.snapshot()["sim_time_s"]))


@router.get(
    "/current/detectors",
    response_model=list[DetectorV1],
    operation_id="runs_detectors",
    responses=NO_RUN,
)
def detectors() -> list[DetectorV1]:
    return [DetectorV1.model_validate(d) for d in _live().detectors()]


@router.patch(
    "/current/detectors/{detector_type}",
    response_model=list[DetectorV1],
    operation_id="runs_toggle_detector",
    dependencies=[Depends(require_admin)],
    responses={**NO_RUN, 404: {"model": ErrorEnvelope, "description": "Unknown detector"}},
)
def toggle_detector(detector_type: str, body: DetectorToggleV1) -> list[DetectorV1]:
    """Admin: switch a detector on or off for the live run."""
    live = _live()
    try:
        live.set_detector(detector_type, body.enabled)
    except KeyError:
        raise ApiError(404, "unknown_detector", f"Unknown detector '{detector_type}'") from None
    return [DetectorV1.model_validate(d) for d in live.detectors()]


@router.get(
    "/current/graph", response_model=GraphSnapshotV1, operation_id="runs_graph", responses=NO_RUN
)
def graph(
    max_users: int = Query(400, ge=10, le=3000),
    window_s: float = Query(60.0, gt=0, le=86_400),
    oracle: bool = Query(False, description="Add the answer key (simulator ground truth)"),
) -> GraphSnapshotV1:
    """Windowed graph of the live run, capped at `max_users` users."""
    return GraphSnapshotV1.model_validate(_live().graph_snapshot(max_users, window_s, oracle))
