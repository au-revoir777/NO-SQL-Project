"""
Starting a live run, shared by POST /runs/start (M7 dashboard) and
POST /api/v1/runs (web app). A lock serialises run management, so two start
requests cannot interleave and leave two players running.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fraudsim.api.live import LiveRun
from fraudsim.api.state import state
from fraudsim.api.v1.stream.publisher import StreamPublisher
from fraudsim.simulator.scenario_loader import list_scenarios
from fraudsim.types import new_run_id

run_lock = asyncio.Lock()


class UnknownScenarioError(LookupError):
    pass


async def start_live_run(scenario: str, seed: int, speed: float) -> str:
    """Stop the current run (if any) and start a new one; return its run id."""
    if scenario not in list_scenarios():
        raise UnknownScenarioError(scenario)
    async with run_lock:
        if state.live is not None:
            await state.live.stop()
            state.live = None
        state.run_id = new_run_id()
        state.scenario = scenario
        state.seed = seed
        state.speed_multiplier = speed
        state.events_emitted = 0
        state.active_rings.clear()
        state.live = LiveRun(
            scenario=scenario,
            seed=seed,
            run_id=state.run_id,
            speed=speed,
            # WebSocket fan-out as before, plus the P3 streams (alerts, KPIs, events).
            broadcast=StreamPublisher(state.run_id, lambda: state.live, state.broadcast_ws),
            log_dir=Path(os.environ.get("FRAUDSIM_RUNS_DIR", "runs")) / "live" / state.run_id,
        )
        await state.live.start()
        await state.broadcast_ws(
            {"type": "RUN_STARTED", "run_id": state.run_id, "scenario": scenario, "seed": seed}
        )
        return state.run_id
