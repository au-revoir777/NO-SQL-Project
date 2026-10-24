"""
P4: scenario builder API, run controls and replays.

- invalid configs are rejected with field-level errors;
- a scenario round-trips through the YAML export and the scenario loader to the
  same config hash;
- determinism: demo_story seed 7 started from the web app gives the same stream
  digest as `fraudsim demo-story --seed 7` (the committed story JSON).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import yaml
from auth_fixtures import setup_app_db, sign_in
from fastapi.testclient import TestClient

from fraudsim.api.main import app
from fraudsim.simulator.scenario_loader import list_scenarios, load_scenario
from fraudsim.types import config_hash

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "results" / "demo_story" / "story_00434da7845b.json"


@pytest.fixture
def users(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, tuple[str, str]]:
    monkeypatch.setenv("FRAUDSIM_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("SCENARIOS_CUSTOM_DIR", str(tmp_path / "custom"))
    return setup_app_db(tmp_path, monkeypatch)


def client(users: dict[str, tuple[str, str]], role: str = "analyst") -> TestClient:
    c = TestClient(app, base_url="https://testserver")
    sign_in(c, *users[role])
    return c


def minimal(**sim: object) -> dict[str, object]:
    return {
        "name": "built_in_form",
        "simulation": {"duration_seconds": 30, "target_event_rate": 10.0, "num_users": 40, **sim},
        "rings": [{"id": "r1", "type": "shared_device", "size": 3, "spawn_time_s": 5}],
    }


# ─── Validation ───────────────────────────────────────────────────────────────


def test_invalid_configs_are_rejected_with_field_level_errors(users: dict) -> None:
    c = client(users)
    bad = minimal(num_users=-5, heavy_tail_alpha=0.5)
    bad["rings"] = [{"id": "r1", "type": "not_a_type", "size": 1}]  # type: ignore[index]
    bad["simulation"]["typo_field"] = 3  # type: ignore[index]
    resp = c.post("/api/v1/scenarios/validate", json=bad)
    assert resp.status_code == 422
    locs = {tuple(d["loc"]) for d in resp.json()["error"]["details"]}
    assert ("body", "simulation", "num_users") in locs
    assert ("body", "simulation", "heavy_tail_alpha") in locs
    assert ("body", "simulation", "typo_field") in locs  # unknown keys are errors
    assert ("body", "rings", 0, "type") in locs
    assert ("body", "rings", 0, "size") in locs


def test_cross_field_rules_come_from_the_simulator_parser(users: dict) -> None:
    c = client(users)
    dup = minimal()
    dup["rings"] = [  # type: ignore[assignment]
        {"id": "same", "type": "shared_device", "size": 3},
        {"id": "same", "type": "shared_card", "size": 3},
    ]
    resp = c.post("/api/v1/scenarios/validate", json=dup)
    assert resp.status_code == 422 and "duplicate ring ids" in resp.json()["error"]["message"]
    ok = c.post("/api/v1/scenarios/validate", json=minimal())
    assert ok.status_code == 200 and ok.json()["valid"] and ok.json()["events_estimate"] == 300


# ─── Round trip ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", list_scenarios())
def test_presets_round_trip_through_the_api_and_yaml(users: dict, name: str) -> None:
    c = client(users)
    original = config_hash(load_scenario(name))
    body = c.get(f"/api/v1/scenarios/{name}").json()
    assert config_hash(body) == original
    text = c.post("/api/v1/scenarios/yaml", json=body).text
    assert config_hash(yaml.safe_load(text)) == original


def test_a_form_built_scenario_loads_with_the_scenario_loader(users: dict, tmp_path: Path) -> None:
    c = client(users)
    form = minimal(user_join_rate=0.1, hub_distribution={"office_wifi": {"size": 12, "type": "ip"}})
    resp = c.post("/api/v1/scenarios/yaml", json=form)
    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == 'attachment; filename="built_in_form.yaml"'
    (tmp_path / "built_in_form.yaml").write_text(resp.text, encoding="utf-8")
    loaded = load_scenario("built_in_form", tmp_path)
    assert (
        config_hash(loaded) == c.post("/api/v1/scenarios/validate", json=form).json()["config_hash"]
    )


# ─── Custom scenarios (admin) ─────────────────────────────────────────────────


def test_only_admins_save_custom_scenarios(users: dict, tmp_path: Path) -> None:
    analyst, admin = client(users), client(users, "admin")
    assert analyst.put("/api/v1/scenarios/custom/built_in_form", json=minimal()).status_code == 403
    clash = admin.put("/api/v1/scenarios/custom/baseline", json=minimal() | {"name": "baseline"})
    assert clash.status_code == 409  # a preset cannot be overwritten
    mismatch = admin.put("/api/v1/scenarios/custom/other_name", json=minimal())
    assert mismatch.status_code == 422  # path and scenario name must agree
    saved = admin.put("/api/v1/scenarios/custom/built_in_form", json=minimal())
    assert saved.status_code == 200 and saved.json()["custom"] is True
    assert (tmp_path / "custom" / "built_in_form.yaml").exists()
    listed = {s["name"]: s for s in analyst.get("/api/v1/scenarios").json()}
    assert listed["built_in_form"]["custom"] and not listed["baseline"]["custom"]
    assert analyst.get("/api/v1/scenarios/built_in_form").json()["rings"][0]["id"] == "r1"


# ─── Runs ─────────────────────────────────────────────────────────────────────


def wait_finished(c: TestClient, timeout: float = 120) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        cur = c.get("/api/v1/runs/current").json()
        if cur["status"] == "finished":
            return cur
        assert time.monotonic() < deadline, cur
        time.sleep(0.2)


def test_demo_story_from_the_web_app_matches_the_cli_stream_digest(users: dict) -> None:
    cli_digest = json.loads(STORY.read_text(encoding="utf-8"))["meta"]["stream_digest"]
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, *users["analyst"])
        # As a preset name, and as the inline config the builder would send.
        for body in (
            {"scenario": "demo_story", "seed": 7, "speed_multiplier": 0},
            {
                "config": c.get("/api/v1/scenarios/demo_story").json(),
                "seed": 7,
                "speed_multiplier": 0,
            },
        ):
            assert c.post("/api/v1/runs", json=body).status_code == 201
            assert wait_finished(c)["stream_digest"] == cli_digest
        c.post("/api/v1/runs/current/stop")


def test_run_controls(users: dict) -> None:
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, *users["analyst"])
        c.post("/api/v1/runs", json={"scenario": "baseline", "seed": 3, "speed_multiplier": 1})
        assert c.post("/api/v1/runs/current/pause").json()["status"] == "paused"
        assert c.post("/api/v1/runs/current/resume").json()["status"] == "running"
        assert (
            c.post("/api/v1/runs/current/speed", json={"speed_multiplier": 5}).json()[
                "speed_multiplier"
            ]
            == 5
        )
        assert c.post("/api/v1/runs/current/rate", json={"events_per_second": 0}).status_code == 422
        injected = c.post(
            "/api/v1/runs/current/inject", json={"ring_type": "shared_ip", "evasion": "hub_hiding"}
        )
        assert injected.status_code == 201 and injected.json()["ring_id"]
        graph = c.get("/api/v1/runs/current/graph?max_users=50").json()
        assert graph["shown_users"] <= 50 and "nodes" in graph
        dets = c.get("/api/v1/runs/current/detectors").json()
        assert dets and {"type", "enabled"} <= set(dets[0])
        toggle = c.patch(
            f"/api/v1/runs/current/detectors/{dets[0]['type']}", json={"enabled": False}
        )
        assert toggle.status_code == 403  # analysts cannot change detectors
        assert c.post("/api/v1/runs/current/stop").json()["status"] == "stopped"


def test_admin_toggles_detectors(users: dict) -> None:
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, *users["admin"])
        c.post("/api/v1/runs", json={"scenario": "baseline", "seed": 3, "speed_multiplier": 1})
        name = c.get("/api/v1/runs/current/detectors").json()[0]["type"]
        after = c.patch(f"/api/v1/runs/current/detectors/{name}", json={"enabled": False}).json()
        assert next(d for d in after if d["type"] == name)["enabled"] is False
        assert (
            c.patch("/api/v1/runs/current/detectors/nope", json={"enabled": False}).status_code
            == 404
        )
        c.post("/api/v1/runs/current/stop")


# ─── Replays ──────────────────────────────────────────────────────────────────


def test_replays_list_and_serve_the_demo_story_json(users: dict) -> None:
    c = client(users)
    listed = {r["run_id"]: r for r in c.get("/api/v1/replays").json()}
    assert listed["00434da7845b"]["replayable"] and listed["00434da7845b"]["kind"] == "story"
    got = c.get("/api/v1/replays/00434da7845b").json()
    assert got == json.loads(STORY.read_text(encoding="utf-8"))  # unchanged
    assert c.get("/api/v1/replays/ffffffffffff").status_code == 404
    assert c.get("/api/v1/replays/..%2Fsecrets").status_code in (404, 422)
