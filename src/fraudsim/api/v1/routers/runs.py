"""GET /api/v1/runs/current: the live run, read from the existing engine."""

from __future__ import annotations

from fastapi import APIRouter

from fraudsim.api.state import state
from fraudsim.api.v1.schemas import RunStatusV1

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
