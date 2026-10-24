"""
P5: alert triage and cases.

- state machines of alert and case statuses (invalid transitions rejected);
- feedback labels move the live run's thresholds exactly as AlertPolicy defines;
- after a scripted triage session the audit chain verifies (API and CLI).
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from auth_fixtures import setup_app_db, sign_in
from click.testing import CliRunner
from fastapi.testclient import TestClient

from fraudsim.api.main import app
from fraudsim.api.state import state
from fraudsim.api.v1.cases.workflow import check_alert, check_case
from fraudsim.api.v1.errors import ApiError
from fraudsim.appdb.models import AlertStatus as A
from fraudsim.appdb.models import CaseStatus as C
from fraudsim.cli import main as cli

# ─── State machines ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("old", "new", "ok"),
    [
        (A.NEW, A.TRIAGED, True),
        (A.NEW, A.CLOSED, True),
        (A.TRIAGED, A.ESCALATED, True),
        (A.ESCALATED, A.TRIAGED, True),
        (A.TRIAGED, A.NEW, False),
        (A.CLOSED, A.TRIAGED, False),
        (A.CLOSED, A.NEW, False),
        (A.TRIAGED, A.TRIAGED, True),  # no-op
    ],
)
def test_alert_transitions(old: A, new: A, ok: bool) -> None:
    if ok:
        check_alert(old, new, is_admin=False)
    else:
        with pytest.raises(ApiError) as e:
            check_alert(old, new, is_admin=False)
        assert e.value.status == 409 and e.value.code == "invalid_transition"


def test_only_admins_reopen() -> None:
    check_alert(A.CLOSED, A.TRIAGED, is_admin=True)
    check_case(C.CLOSED, C.IN_REVIEW, is_admin=True, resolution=None)
    with pytest.raises(ApiError):
        check_case(C.CLOSED, C.OPEN, is_admin=True, resolution=None)


@pytest.mark.parametrize(
    ("old", "new", "ok"),
    [
        (C.OPEN, C.IN_REVIEW, True),
        (C.IN_REVIEW, C.OPEN, True),
        (C.OPEN, C.ESCALATED, True),
        (C.ESCALATED, C.IN_REVIEW, True),
        (C.ESCALATED, C.OPEN, False),
        (C.CLOSED, C.ESCALATED, False),
    ],
)
def test_case_transitions(old: C, new: C, ok: bool) -> None:
    if ok:
        check_case(old, new, is_admin=False, resolution=None)
    else:
        with pytest.raises(ApiError):
            check_case(old, new, is_admin=False, resolution=None)


def test_closing_a_case_needs_a_resolution() -> None:
    with pytest.raises(ApiError) as e:
        check_case(C.IN_REVIEW, C.CLOSED, is_admin=False, resolution="  ")
    assert e.value.status == 422
    check_case(C.IN_REVIEW, C.CLOSED, is_admin=False, resolution="Confirmed ring; accounts blocked")


# ─── A real run, then a triage session through the API ────────────────────────


@pytest.fixture(scope="module")
def session(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict]:
    tmp = tmp_path_factory.mktemp("p5")
    mp = pytest.MonkeyPatch()
    mp.setenv("FRAUDSIM_RUNS_DIR", str(tmp / "runs"))
    users = setup_app_db(tmp, mp)
    with TestClient(app, base_url="https://testserver") as c:
        sign_in(c, *users["analyst"])
        run_id = c.post(
            "/api/v1/runs", json={"scenario": "baseline", "seed": 7, "speed_multiplier": 0}
        ).json()["run_id"]
        deadline = time.monotonic() + 120
        while c.get("/api/v1/runs/current").json()["status"] != "finished":
            assert time.monotonic() < deadline
            time.sleep(0.2)
        admin = TestClient(app, base_url="https://testserver")
        sign_in(admin, *users["admin"])
        yield {"c": c, "admin": admin, "run_id": run_id, "tmp": tmp, "users": users}
    mp.undo()


def test_a_run_records_its_alerts(session: dict) -> None:
    page = session["c"].get("/api/v1/alerts", params={"run_id": session["run_id"]}).json()
    assert page["total"] >= 2
    first = page["items"][0]
    assert first["status"] == "new" and first["kind"] in ("alert", "early_warning")
    assert first["members_count"] >= 2 and first["detectors"] and first["reason"]
    risks = [a["risk"] for a in page["items"]]
    assert risks == sorted(risks, reverse=True)  # default sort: risk, descending
    detail = session["c"].get(f"/api/v1/alerts/{first['id']}").json()
    assert detail["explanation"]["evidence_subgraph"]["nodes"]
    assert detail["live"] is True and detail["history"]


def test_filters(session: dict) -> None:
    c = session["c"]
    all_ = c.get("/api/v1/alerts").json()["items"]
    lo = c.get("/api/v1/alerts", params={"risk_min": 0.9}).json()["items"]
    assert all(a["risk"] >= 0.9 for a in lo) and len(lo) <= len(all_)
    det = all_[0]["detectors"][0]
    assert all(
        det in a["detectors"]
        for a in c.get("/api/v1/alerts", params={"detector": det}).json()["items"]
    )
    one = all_[0]["alert_ref"]
    assert [a["alert_ref"] for a in c.get("/api/v1/alerts", params={"q": one}).json()["items"]] == [
        one
    ]
    page = c.get("/api/v1/alerts", params={"limit": 1}).json()
    assert len(page["items"]) == 1 and (page["next_cursor"] == "1" or page["total"] == 1)


def test_saved_views_are_per_user(session: dict) -> None:
    c, admin = session["c"], session["admin"]
    v = c.put(
        "/api/v1/alerts/views", json={"name": "high risk", "filters": {"risk_min": 0.8}}
    ).json()
    assert [x["name"] for x in c.get("/api/v1/alerts/views").json()] == ["high risk"]
    assert admin.get("/api/v1/alerts/views").json() == []
    assert admin.delete(f"/api/v1/alerts/views/{v['id']}").status_code == 404
    assert c.delete(f"/api/v1/alerts/views/{v['id']}").status_code == 204


def test_feedback_moves_thresholds_exactly_as_the_alert_policy(session: dict) -> None:
    c = session["c"]
    alert = c.get("/api/v1/alerts", params={"run_id": session["run_id"]}).json()["items"][-1]
    policy = state.live.scoring.policy  # type: ignore[union-attr]
    expected = copy.deepcopy(policy).feedback(
        alert["alert_ref"], alert["ring_type"], float(alert["risk"]), "dismiss"
    )
    resp = c.post(f"/api/v1/alerts/{alert['id']}/labels", json={"label": "dismissed_benign"}).json()
    got = resp["threshold_adaptation"]
    assert {k: v for k, v in got.items() if k != "ts"} == {
        k: v for k, v in expected.items() if k != "ts"
    }
    assert policy.threshold(alert["ring_type"]) == pytest.approx(expected["threshold_after"])
    needs = c.post(f"/api/v1/alerts/{alert['id']}/labels", json={"label": "needs_info"}).json()
    assert needs["threshold_adaptation"] is None and needs["label"]["label"] == "needs_info"


def test_scripted_triage_session_keeps_the_audit_chain_valid(session: dict) -> None:
    c, admin = session["c"], session["admin"]
    me = c.get("/api/v1/auth/me").json()["user"]
    items = c.get("/api/v1/alerts", params={"run_id": session["run_id"]}).json()["items"]
    a1, a2 = items[0], items[1]

    # Triage the first alert: assign, status, note, edit the note, label.
    assert (
        c.patch(f"/api/v1/alerts/{a1['id']}", json={"assignee_id": me["id"]}).json()["assignee"][
            "id"
        ]
        == me["id"]
    )
    assert (
        c.patch(f"/api/v1/alerts/{a1['id']}", json={"status": "triaged"}).json()["status"]
        == "triaged"
    )
    bad = c.patch(f"/api/v1/alerts/{a1['id']}", json={"status": "new"})
    assert bad.status_code == 409 and bad.json()["error"]["code"] == "invalid_transition"
    note = c.post(
        f"/api/v1/alerts/{a1['id']}/notes", json={"body": "Shares **one device**."}
    ).json()
    edited = c.patch(f"/api/v1/notes/{note['id']}", json={"body": "Shares one device and a card."})
    assert (
        edited.json()["edited"]
        and edited.json()["revisions"][0]["body"] == "Shares **one device**."
    )
    assert c.patch(f"/api/v1/notes/{note['id']}", json={"body": "again"}).status_code == 409
    c.post(f"/api/v1/alerts/{a1['id']}/labels", json={"label": "confirmed_fraud"})

    # A case from two alerts; its evidence snapshot hash is in the audit trail.
    case = c.post(
        "/api/v1/cases",
        json={
            "title": "Device ring in baseline",
            "alert_ids": [a1["id"], a2["id"]],
            "priority": "high",
        },
    ).json()
    assert case["status"] == "open" and len(case["alerts"]) == 2
    snap = c.get(f"/api/v1/cases/{case['id']}/alerts/{a1['id']}/snapshot").json()
    canonical = json.dumps(snap["snapshot"], sort_keys=True, separators=(",", ":"), default=str)
    assert hashlib.sha256(canonical.encode()).hexdigest() == snap["sha256"]
    attached = [h for h in case["history"] if h["action_type"] == "CASE_ALERT_ATTACHED"]
    assert snap["sha256"] in {h["details"]["snapshot_sha256"] for h in attached}

    c.post(f"/api/v1/cases/{case['id']}/notes", json={"body": "Escalating to the fraud team."})
    assert (
        c.patch(f"/api/v1/cases/{case['id']}", json={"status": "escalated"}).json()["status"]
        == "escalated"
    )
    assert c.patch(f"/api/v1/cases/{case['id']}", json={"status": "open"}).status_code == 409
    assert c.patch(f"/api/v1/cases/{case['id']}", json={"status": "closed"}).status_code == 422
    closed = c.patch(
        f"/api/v1/cases/{case['id']}", json={"status": "closed", "resolution": "Accounts blocked"}
    ).json()
    assert closed["status"] == "closed" and closed["resolution"] == "Accounts blocked"
    assert (
        c.post(
            f"/api/v1/cases/{case['id']}/alerts", json={"alert_ids": [items[2]["id"]]}
        ).status_code
        == 409
    )
    assert c.patch(f"/api/v1/cases/{case['id']}", json={"status": "in_review"}).status_code == 409
    assert (
        admin.patch(f"/api/v1/cases/{case['id']}", json={"status": "in_review"}).status_code == 200
    )

    # Bulk: close what is left; one already-closed alert is reported, not fatal.
    c.patch(f"/api/v1/alerts/{a2['id']}", json={"status": "closed"})
    res = c.post(
        "/api/v1/alerts/bulk",
        json={"ids": [a2["id"], items[2]["id"]], "action": "status", "status": "triaged"},
    ).json()
    assert res["updated"] == [items[2]["id"]] and res["rejected"][0]["id"] == a2["id"]

    # The admin audit view lists the session, and the chain verifies.
    assert c.get("/api/v1/audit").status_code == 403
    actions = {
        e["action_type"] for e in admin.get("/api/v1/audit", params={"limit": 1000}).json()["items"]
    }
    assert {
        "ALERT_ASSIGNED",
        "ALERT_STATUS",
        "NOTE_ADDED",
        "NOTE_EDITED",
        "ALERT_LABELED",
        "CASE_CREATED",
        "CASE_ALERT_ATTACHED",
        "CASE_UPDATED",
    } <= actions
    verify = admin.get("/api/v1/audit/verify").json()
    assert verify["ok"] and verify["entries"] > 10
    out = CliRunner().invoke(cli, ["audit-verify", str(Path(session["tmp"]) / "app_audit")])
    assert out.exit_code == 0, out.output


def test_cases_list_and_users(session: dict) -> None:
    c = session["c"]
    page = c.get("/api/v1/cases").json()
    assert page["total"] >= 1 and page["items"][0]["alerts_count"] >= 1
    assert {u["email"] for u in c.get("/api/v1/users").json()} >= {
        session["users"]["admin"][0],
        session["users"]["analyst"][0],
    }
