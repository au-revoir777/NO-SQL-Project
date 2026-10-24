"""
/api/v1/replays: recorded runs and the story replays of `fraudsim demo-story` (P4).

A replay is the JSON `fraudsim demo-story` writes (`story_<run_id>.json`): the
recorded flags of each detector, the ground truth and the graph of one run.
They are searched in REPLAY_DIRS (os.pathsep-separated; default the committed
`results/demo_story/` and the local `demo/`). Recorded live and CLI runs
(`runs/**/manifest.json`) are listed too, marked `replayable: false` until a
story has been generated for them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi import Path as PathParam
from pydantic import BaseModel

from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope

router = APIRouter(prefix="/replays", tags=["replays"])

ROOT = Path(__file__).resolve().parents[5]
RUN_ID = r"^[0-9a-f]{6,32}$"


class ReplaySummary(BaseModel):
    run_id: str
    kind: str  # story | run
    replayable: bool
    scenario: str | None
    seed: int | None
    events: int | None
    duration_s: float | None
    generated_at: str | None
    source: str


def replay_dirs() -> list[Path]:
    raw = os.environ.get("REPLAY_DIRS")
    if raw:
        return [Path(p) for p in raw.split(os.pathsep) if p]
    return [ROOT / "results" / "demo_story", ROOT / "demo"]


def runs_dir() -> Path:
    return Path(os.environ.get("FRAUDSIM_RUNS_DIR", str(ROOT / "runs")))


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _stories() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for d in replay_dirs():
        for p in sorted(d.glob("story_*.json")) if d.is_dir() else []:
            found.setdefault(p.stem.removeprefix("story_"), p)  # earlier dirs win
    return found


@router.get("", response_model=list[ReplaySummary], operation_id="replays_list")
def replays() -> list[ReplaySummary]:
    out: list[ReplaySummary] = []
    stories = _stories()
    for run_id, path in stories.items():
        meta = json.loads(path.read_text(encoding="utf-8")).get("meta", {})
        out.append(
            ReplaySummary(
                run_id=run_id,
                kind="story",
                replayable=True,
                scenario=meta.get("scenario"),
                seed=meta.get("seed"),
                events=meta.get("events"),
                duration_s=meta.get("duration_s"),
                generated_at=meta.get("generated_at"),
                source=_rel(path),
            )
        )
    base = runs_dir()
    manifests = sorted(base.glob("*/manifest.json")) + sorted(base.glob("live/*/manifest.json"))
    for path in manifests if base.is_dir() else []:
        try:
            m: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        run_id = str(m.get("run_id", path.parent.name))
        if run_id in stories:
            continue
        out.append(
            ReplaySummary(
                run_id=run_id,
                kind="run",
                replayable=False,
                scenario=m.get("scenario"),
                seed=m.get("seed"),
                events=m.get("events"),
                duration_s=m.get("sim_time_s"),
                generated_at=m.get("finished_at") or m.get("started_at"),
                source=_rel(path),
            )
        )
    return out


@router.get(
    "/{run_id}",
    operation_id="replays_get",
    responses={
        200: {"description": "The story JSON written by `fraudsim demo-story`, unchanged"},
        404: {"model": ErrorEnvelope, "description": "No story replay for this run"},
    },
)
def replay(run_id: str = PathParam(pattern=RUN_ID)) -> dict[str, Any]:
    path = _stories().get(run_id)
    if path is None:
        raise ApiError(
            404,
            "no_replay",
            f"No story replay for run {run_id}; generate one with `fraudsim demo-story`",
        )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data
