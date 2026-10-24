"""GET /api/v1/runs/current and /runs/current/metrics: the live run, read from the engine."""

from __future__ import annotations

from fastapi import APIRouter

from fraudsim.api.state import state
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope, RunStatusV1
from fraudsim.api.v1.schemas.stream import RunMetricsV1
from fraudsim.api.v1.stream.publisher import kpis

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/current", response_model=RunStatusV1, operation_id="runs_current")
async def current_run() -> RunStatusV1:
    live = state.live
    snap = live.snapshot() if live is not None else {}
    return RunStatusV1(
        run_id=state.run_id,
        status=live.status if live is not None else state.status,
        scenario=state.scenario,
        seed=state.seed,
        events_emitted=int(snap.get("events_emitted", state.events_emitted)),
        rings_tracked=len(live.engine.tracker.active()) if live is not None else 0,
        sim_time_s=float(snap.get("sim_time_s", 0.0)),
        speed_multiplier=float(snap.get("speed_multiplier", state.speed_multiplier)),
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
