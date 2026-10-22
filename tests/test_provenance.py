"""R3 (M0 audit): every experiment run leaves a manifest entry, also when it fails."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraudsim.experiments.harness import run_grid
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.experiments.suite import baseline_methods


def entries(out: Path) -> list[dict]:
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))["grids"]


def test_completed_run_is_recorded_with_provenance(tmp_path: Path) -> None:
    with recorded(tmp_path, "unit", {"seeds": [1]}) as entry:
        (tmp_path / "results.csv").write_text("a\n1\n2\n", encoding="utf-8")
        entry["note"] = "added by the caller"
    (e,) = entries(tmp_path)
    assert e["status"] == "complete" and e["error"] is None
    assert e["experiment"] == "unit" and e["seeds"] == [1] and e["note"] == "added by the caller"
    assert e["rows"] == 2
    assert len(e["git_commit"]) == 40 and isinstance(e["git_dirty"], bool)
    assert e["started_at"] <= e["ended_at"] and e["wall_s"] >= 0
    assert e["python"] and e["libraries"]["numpy"]


def test_failed_run_is_recorded_and_the_error_propagates(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"), recorded(tmp_path, "unit", {}):
        raise RuntimeError("boom")
    with recorded(tmp_path, "unit", {}):
        pass
    failed, ok = entries(tmp_path)  # entries are appended, never rewritten
    assert failed["status"] == "failed" and failed["error"]["type"] == "RuntimeError"
    assert failed["error"]["message"] == "boom" and failed["rows"] == 0
    assert ok["status"] == "complete"


def test_paths_in_manifests_are_repo_relative() -> None:
    assert repo_relative(Path(__file__)) == "tests/test_provenance.py"


def test_run_grid_writes_a_complete_manifest(tmp_path: Path) -> None:
    methods = [m for m in baseline_methods() if m.name == "static_cap10"]
    run_grid(
        "tiny",
        ["baseline"],
        [1],
        methods,
        tmp_path,
        scenario_overrides={"simulation.duration_seconds": 10, "simulation.num_users": 60},
        log=lambda _: None,
    )
    (e,) = entries(tmp_path / "tiny")
    assert e["status"] == "complete" and e["rows"] == 1
    assert e["scenarios"] == ["baseline"] and e["seeds"] == [1]
    assert e["methods"][0]["name"] == "static_cap10"
    assert e["model"] is None or not Path(e["model"]["path"]).is_absolute()
