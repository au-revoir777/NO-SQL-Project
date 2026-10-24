"""
/api/v1/reports: build an investigation report (HTML or PDF), list them, and
download them again. Each report gets an id, the run ids and scenario config
hashes it used, the SHA-256 of its file, and an app audit entry.

Files live in $FRAUDSIM_RUNS_DIR/app_reports/<id>.<html|pdf>, with <id>.json
(the report's numbers without the charts) beside them.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from fraudsim.api.state import state
from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.deps import DB, CurrentUser, client_ip
from fraudsim.api.v1.cases import service as svc
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope, Page
from fraudsim.api.v1.schemas.reports import ReportCreate, ReportOut
from fraudsim.appdb.models import Report
from fraudsim.reports.builder import ReportError, ReportRequest, collect, render_html, render_pdf
from fraudsim.reports.run_logs import runs_root

router = APIRouter(prefix="/reports", tags=["reports"])

ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Unknown report, case or alert"},
    503: {"model": ErrorEnvelope, "description": "PDF rendering is not available"},
}
MEDIA = {"html": "text/html; charset=utf-8", "pdf": "application/pdf"}


def reports_dir() -> Path:
    d = runs_root() / "app_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _out(db: Any, r: Report) -> ReportOut:
    path = Path(r.path)
    meta_path = path.with_suffix(".json")
    rings = 0
    if meta_path.exists():
        rings = int(json.loads(meta_path.read_text(encoding="utf-8")).get("rings", 0))
    return ReportOut(
        id=r.id,
        title=r.title,
        format=r.format,  # type: ignore[arg-type]
        scope=r.scope,
        run_ids=list(r.run_ids),
        config_hashes=list(r.config_hashes),
        sha256=r.sha256,
        size_bytes=path.stat().st_size if path.exists() else 0,
        created_by=svc.user_ref(db, r.created_by_id),
        created_at=r.created_at,
        rings=rings,
    )


def _numbers(model: dict[str, Any]) -> dict[str, Any]:
    """The report's numbers without charts (written next to the file)."""
    return {
        "title": model["title"],
        "scope": model["scope"],
        "sections": model["sections"],
        "run_ids": model["run_ids"],
        "config_hashes": model["config_hashes"],
        "summary": model["summary"],
        "runs": model["runs"],
        "rings": len(model["rings"]),
        "ring_ids": [[r["run_id"], r["ring_id"]] for r in model["rings"]],
    }


@router.post(
    "",
    response_model=ReportOut,
    status_code=201,
    operation_id="reports_create",
    responses=ERRORS,
)
def create(body: ReportCreate, request: Request, db: DB, user: CurrentUser) -> ReportOut:
    if not (body.run_ids or body.alert_ids or body.case_ids):
        raise ApiError(422, "validation_error", "Choose at least one run, alert or case")
    req = ReportRequest(
        title=body.title,
        run_ids=body.run_ids,
        alert_ids=body.alert_ids,
        case_ids=body.case_ids,
        since=body.since,
        until=body.until,
        sections=list(body.sections),
        oracle=body.oracle,
        format=body.format,
    )
    live = state.live
    if live is not None:
        live.sync_logs()  # the current run's logs as they stand now
    try:
        model = collect(db, req)
    except ReportError as e:
        raise ApiError(404 if e.code == "not_found" else 422, e.code, str(e)) from e
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    html = render_html(model, generated_at)
    try:
        data = render_pdf(html) if body.format == "pdf" else html.encode("utf-8")
    except ReportError as e:
        raise ApiError(503, e.code, str(e)) from e
    rid = uuid.uuid4().hex
    path = reports_dir() / f"{rid}.{body.format}"
    path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    path.with_suffix(".json").write_text(
        json.dumps({**_numbers(model), "sha256": sha, "generated_at": generated_at}, indent=2),
        encoding="utf-8",
    )
    row = Report(
        id=rid,
        title=body.title,
        scope=model["scope"] | {"sections": model["sections"]},
        run_ids=model["run_ids"],
        config_hashes=model["config_hashes"],
        format=body.format,
        path=str(path),
        sha256=sha,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        "REPORT_GENERATED",
        str(user.email),
        "report",
        rid,
        {
            "title": body.title,
            "format": body.format,
            "sha256": sha,
            "run_ids": model["run_ids"],
            "config_hashes": model["config_hashes"],
            "case_ids": body.case_ids,
            "alert_ids": body.alert_ids,
            "rings": len(model["rings"]),
            "ip": client_ip(request),
        },
        db,
    )
    db.commit()
    return _out(db, row)


@router.get("", response_model=Page[ReportOut], operation_id="reports_list")
def reports(
    db: DB,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> Page[ReportOut]:
    total = db.scalar(select(func.count()).select_from(Report)) or 0
    start = int(cursor) if cursor and cursor.isdigit() else 0
    rows = db.scalars(
        select(Report).order_by(Report.created_at.desc(), Report.id).offset(start).limit(limit)
    ).all()
    nxt = str(start + limit) if start + limit < total else None
    return Page[ReportOut](items=[_out(db, r) for r in rows], next_cursor=nxt, total=total)


def _get(db: Any, report_id: str) -> Report:
    r: Report | None = db.get(Report, report_id)
    if r is None:
        raise ApiError(404, "not_found", f"No report {report_id!r}")
    return r


@router.get("/{report_id}", response_model=ReportOut, operation_id="reports_get", responses=ERRORS)
def report(report_id: str, db: DB) -> ReportOut:
    return _out(db, _get(db, report_id))


@router.get(
    "/{report_id}/download",
    operation_id="reports_download",
    responses={
        **ERRORS,
        200: {
            "content": {"text/html": {}, "application/pdf": {}},
            "description": "The report file, as generated (its SHA-256 is in the report record)",
        },
    },
    response_class=FileResponse,
)
async def download(report_id: str, db: DB) -> FileResponse:
    r = await run_in_threadpool(_get, db, report_id)
    path = Path(r.path)
    if not path.exists():
        raise ApiError(404, "not_found", "The report file is missing on the server")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in r.title)[:60] or "report"
    return FileResponse(
        path,
        media_type=MEDIA[r.format],
        filename=f"{safe}-{r.id[:8]}.{r.format}",
    )
