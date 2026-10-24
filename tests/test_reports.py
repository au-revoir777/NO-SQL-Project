"""
P7: investigation reports.

- every run number in a report equals the same number recomputed here from the
  run's log files (independently of fraudsim.reports.run_logs);
- the report record lists every run it used, and its file hash is in the audit;
- golden: the HTML report of a fixed seed is byte-stable apart from the
  timestamp, and matches tests/golden/ (charts excluded, see below).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from auth_fixtures import setup_app_db, sign_in
from fastapi.testclient import TestClient

from fraudsim.api.live import load_default_scorer
from fraudsim.api.main import app
from fraudsim.api.v1.auth import audit
from fraudsim.detectors.runner import run_detection
from fraudsim.reports.builder import (
    DISCLAIMER,
    ReportRequest,
    chromium_path,
    collect,
    render_html,
)
from fraudsim.scoring.stage import ScoringStage

GOLDEN = Path(__file__).parent / "golden" / "report_baseline_seed7.html"
RUN_ID = "golden-seed7"


def headless_run(root: Path) -> Path:
    run_detection(
        "baseline", 7, root, run_id=RUN_ID, scoring=ScoringStage(scorer=load_default_scorer())
    )
    return root


def logs_only_report(root: Path, stamp: str) -> str:
    model = collect(
        None, ReportRequest(title="Baseline, seed 7", run_ids=[RUN_ID], oracle=True), root
    )
    return render_html(model, stamp)


def recount(run_dir: Path) -> dict[str, Any]:
    """The run numbers, recomputed straight from the JSONL files."""
    events = [json.loads(x) for x in (run_dir / "events.jsonl").read_text().splitlines() if x]
    dets = [json.loads(x) for x in (run_dir / "detections.jsonl").read_text().splitlines() if x]
    txns = [e for e in events if e["event_type"] == "transaction"]
    changes = Counter(d["change"] for d in dets)
    return {
        "events": len(events),
        "transactions": len(txns),
        "transaction_amount": round(sum(e["payload"]["amount"] for e in txns), 2),
        "ring_updates": len(dets),
        "rings_tracked": len({d["ring_id"] for d in dets}),
        "alerts_raised": changes["alert"],
        "early_warnings_raised": changes["early_warning"],
        "events_by_type": dict(Counter(e["event_type"] for e in events)),
    }


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    return (
        headless_run(tmp_path_factory.mktemp("a")),
        headless_run(tmp_path_factory.mktemp("b")),
    )


def test_report_numbers_equal_the_run_logs(two_runs: tuple[Path, Path]) -> None:
    root, _ = two_runs
    model = collect(None, ReportRequest(title="t", run_ids=[RUN_ID], oracle=True), root)
    facts = model["runs"][0]["facts"]
    expected = recount(root / RUN_ID)
    for key, value in expected.items():
        assert facts[key] == value, key
    html = render_html(model, "T")
    assert f'data-metric="events">{expected["events"]:,}<' in html
    assert f'data-metric="transactions">{expected["transactions"]:,} ' in html
    # Every ring raised in the run is in the report, once.
    raised = {
        json.loads(x)["ring_id"]
        for x in (root / RUN_ID / "detections.jsonl").read_text().splitlines()
        if x and json.loads(x)["change"] in ("alert", "early_warning")
    }
    assert {r["ring_id"] for r in model["rings"]} == raised
    # Oracle section only on request, and labelled.
    assert facts["oracle"]["label"] == "Oracle (simulator ground truth)"
    assert facts["oracle"]["true_rings"] == len(
        (root / RUN_ID / "ground_truth.jsonl").read_text().splitlines()
    )
    plain = collect(None, ReportRequest(title="t", run_ids=[RUN_ID]), root)
    assert "oracle" not in plain["runs"][0]["facts"]
    assert "Oracle (simulator ground truth)</h3>" not in render_html(plain, "T")
    assert html.count(DISCLAIMER) >= 3  # header box, page footer (@page), closing footer


def _mask(html: str) -> str:
    return re.sub(r'<span id="generated-at">[^<]*</span>', '<span id="generated-at">*</span>', html)


def _no_charts(html: str) -> str:
    # matplotlib's SVG path data can differ between matplotlib versions, so the
    # committed golden file leaves the charts out (they are compared byte for
    # byte between two builds in test_golden_html_is_byte_stable instead).
    return re.sub(r"<svg.*?</svg>", "<svg/>", _mask(html), flags=re.S)


def test_golden_html_is_byte_stable(two_runs: tuple[Path, Path]) -> None:
    a = logs_only_report(two_runs[0], "2026-10-25T00:00:00+00:00")
    b = logs_only_report(two_runs[1], "2030-01-01T12:34:56+00:00")
    assert a != b  # the timestamp differs ...
    assert _mask(a) == _mask(b)  # ... and nothing else
    if not GOLDEN.exists():  # pragma: no cover - first run writes it
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(_no_charts(a), encoding="utf-8", newline="\n")
    assert _no_charts(a) == GOLDEN.read_text(encoding="utf-8")


# ─── API ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    tmp = tmp_path_factory.mktemp("p7")
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
        yield {"c": c, "run_id": run_id, "tmp": tmp}
    mp.undo()


def _h(c: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": c.cookies.get("fraudsim_csrf") or ""}


def test_case_report_records_runs_hash_and_audit(api: dict[str, Any]) -> None:
    c, run_id = api["c"], api["run_id"]
    alert = c.get("/api/v1/alerts").json()["items"][0]
    case = c.post(
        "/api/v1/cases",
        json={"title": "Report test case", "alert_ids": [alert["id"]]},
        headers=_h(c),
    ).json()
    c.post(
        f"/api/v1/cases/{case['id']}/notes",
        json={"body": "Narrative: accounts opened together."},
        headers=_h(c),
    )
    r = c.post(
        "/api/v1/reports",
        json={"title": "Case report", "case_ids": [case["id"]], "oracle": True},
        headers=_h(c),
    )
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["run_ids"] == [run_id] and rep["rings"] == 1 and len(rep["config_hashes"]) == 1

    dl = c.get(f"/api/v1/reports/{rep['id']}/download")
    assert dl.status_code == 200 and dl.headers["content-type"].startswith("text/html")
    assert hashlib.sha256(dl.content).hexdigest() == rep["sha256"]
    html = dl.text
    assert "Narrative: accounts opened together." in html
    snapshot = c.get(f"/api/v1/cases/{case['id']}").json()["alerts"][0]["snapshot_sha256"]
    assert snapshot in html  # the frozen evidence is cited by hash

    entry = [e for e in audit.trail().read_entries() if e.ring_id == f"report:{rep['id']}"]
    assert len(entry) == 1 and entry[0].action_type == "REPORT_GENERATED"
    assert entry[0].details["sha256"] == rep["sha256"]
    assert entry[0].details["run_ids"] == [run_id]

    # The numbers file next to the report equals a recount of the run's logs.
    numbers = json.loads(
        (Path(api["tmp"]) / "runs" / "app_reports" / f"{rep['id']}.json").read_text()
    )
    facts = numbers["runs"][0]["facts"]
    for key, value in recount(Path(api["tmp"]) / "runs" / "live" / run_id).items():
        assert facts[key] == value, key

    listed = c.get("/api/v1/reports").json()
    assert rep["id"] in {x["id"] for x in listed["items"]}


def test_report_validation(api: dict[str, Any]) -> None:
    c = api["c"]
    r = c.post("/api/v1/reports", json={"title": "Empty"}, headers=_h(c))
    assert r.status_code == 422
    r = c.post("/api/v1/reports", json={"title": "No case", "case_ids": [999]}, headers=_h(c))
    assert r.status_code == 404
    r = c.post(
        "/api/v1/reports",
        json={"title": "Bad", "run_ids": [api["run_id"]], "sections": ["nope"]},
        headers=_h(c),
    )
    assert r.status_code == 422
    assert c.get("/api/v1/reports/nope/download").status_code == 404


@pytest.mark.skipif(chromium_path() is None, reason="no headless Chromium for PDF printing")
def test_pdf_report(api: dict[str, Any]) -> None:
    c = api["c"]
    r = c.post(
        "/api/v1/reports",
        json={"title": "Run report", "run_ids": [api["run_id"]], "format": "pdf"},
        headers=_h(c),
    )
    assert r.status_code == 201, r.text
    dl = c.get(f"/api/v1/reports/{r.json()['id']}/download")
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content.startswith(b"%PDF-") and len(dl.content) > 10_000
    assert hashlib.sha256(dl.content).hexdigest() == r.json()["sha256"]
