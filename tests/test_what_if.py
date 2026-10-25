"""P11: POST /api/v1/alerts/{id}/what-if re-scores an alert with the deployed scorer."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from auth_fixtures import setup_app_db, sign_in
from fastapi.testclient import TestClient

from fraudsim.api.main import app
from fraudsim.api.state import state
from fraudsim.scoring.features import FEATURE_NAMES


@pytest.fixture(scope="module")
def api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    tmp = tmp_path_factory.mktemp("p11")
    mp = pytest.MonkeyPatch()
    mp.setenv("FRAUDSIM_RUNS_DIR", str(tmp / "runs"))
    users = setup_app_db(tmp, mp)
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, *users["analyst"])
        c.post("/api/v1/runs", json={"scenario": "baseline", "seed": 7, "speed_multiplier": 0})
        deadline = time.monotonic() + 120
        while c.get("/api/v1/runs/current").json()["status"] != "finished":
            assert time.monotonic() < deadline
            time.sleep(0.2)
        yield {"c": c}
    mp.undo()


def _h(c: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": c.cookies.get("fraudsim_csrf") or ""}


def _top_alert(c: TestClient) -> dict[str, Any]:
    return c.get("/api/v1/alerts", params={"risk_min": 0.8}).json()["items"][0]


def test_unmodified_vector_returns_exactly_the_scorer_output(api: dict[str, Any]) -> None:
    c = api["c"]
    alert = _top_alert(c)
    r = c.post(f"/api/v1/alerts/{alert['id']}/what-if", json={}, headers=_h(c))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["model"]["from_run"] is True and out["model"]["sha256"]
    # Same as the run's scorer on the scored vector, and as the risk the alert recorded.
    ring = state.live.engine.tracker.rings[alert["alert_ref"]]  # type: ignore[union-attr]
    x = np.asarray([ring.features[f] for f in FEATURE_NAMES])
    expected = float(state.live.scoring.scorer.predict(x)[0])  # type: ignore[union-attr]
    assert out["score"] == expected == out["original_score"]
    assert out["score"] == pytest.approx(alert["risk"])
    assert out["alert"] is True and out["flips"] is False
    assert [f["name"] for f in out["features"]] == list(FEATURE_NAMES)
    assert all(f["value"] == f["original"] for f in out["features"])


def test_applying_a_counterfactual_flips_the_decision(api: dict[str, Any]) -> None:
    c = api["c"]
    alerts = c.get("/api/v1/alerts", params={"risk_min": 0.8}).json()["items"]
    for alert in alerts:
        base = c.post(f"/api/v1/alerts/{alert['id']}/what-if", json={}, headers=_h(c)).json()
        if base["counterfactuals"]:
            break
    else:  # pragma: no cover - depends on the run
        pytest.skip("no alert with a model counterfactual in this run")
    cf = base["counterfactuals"][0]
    assert cf["valid"] is True  # corrected computation (E12 protocol, amendment 1)
    r = c.post(
        f"/api/v1/alerts/{alert['id']}/what-if",
        json={"changes": {cf["feature"]: cf["target"]}},
        headers=_h(c),
    ).json()
    assert r["score"] < r["threshold"] and r["alert"] is False and r["flips"] is True
    changed = {f["name"]: f for f in r["features"]}[cf["feature"]]
    assert changed["value"] == pytest.approx(cf["target"]) and changed["original"] == pytest.approx(
        cf["current"], abs=1e-6
    )


def test_what_if_validation(api: dict[str, Any]) -> None:
    c = api["c"]
    alert = _top_alert(c)
    url = f"/api/v1/alerts/{alert['id']}/what-if"
    r = c.post(url, json={"changes": {"cycle_present": 0.0}}, headers=_h(c))
    assert r.status_code == 422 and "actionable" in r.json()["error"]["message"]
    r = c.post(url, json={"changes": {"size": -1.0}}, headers=_h(c))
    assert r.status_code == 422
    assert c.post("/api/v1/alerts/99999/what-if", json={}, headers=_h(c)).status_code == 404
