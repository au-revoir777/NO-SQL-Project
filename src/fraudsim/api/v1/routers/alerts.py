"""
/api/v1/alerts: the triage queue (P5).

Alerts are persisted as the live run raises them (cases/recorder.py), so the
queue, statuses, assignments, labels and notes survive the run. Every change is
written to the app audit trail. Confirm/dismiss labels go through the live
run's `AlertPolicy.feedback` (the same logic as POST /rings/{id}/feedback) and
return the threshold adaptation; on a run that is no longer live the label is
stored and no threshold changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select

from fraudsim.api.live import ring_payload
from fraudsim.api.state import state
from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.deps import DB, CurrentUser, client_ip
from fraudsim.api.v1.cases import service as svc
from fraudsim.api.v1.cases.workflow import check_alert
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope, Page
from fraudsim.api.v1.schemas.cases import (
    AlertDetail,
    AlertSummary,
    AlertUpdate,
    BulkAlertAction,
    BulkResult,
    LabelIn,
    LabelOut,
    LabelResult,
    NoteIn,
    NoteOut,
    SavedViewIn,
    SavedViewOut,
)
from fraudsim.appdb.models import Alert, AlertStatus, Label, LabelKind, Note, Role, SavedView

router = APIRouter(prefix="/alerts", tags=["alerts"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Not found"}
}
CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorEnvelope, "description": "Transition not allowed"}
}


def _who(user: Any) -> str:
    return str(user.email)


@router.get("", response_model=Page[AlertSummary], operation_id="alerts_list")
def alerts(
    db: DB,
    user: CurrentUser,
    status: Annotated[list[AlertStatus] | None, Query()] = None,
    ring_type: Annotated[list[str] | None, Query()] = None,
    detector: str | None = None,
    risk_min: float | None = Query(None, ge=0, le=1),
    risk_max: float | None = Query(None, ge=0, le=1),
    since: Annotated[
        datetime | None, Query(description="first seen at or after (simulated time)")
    ] = None,
    until: Annotated[datetime | None, Query(description="first seen at or before")] = None,
    run_id: str | None = None,
    assignee: str | None = Query(None, description="me | none | <user id>"),
    q: str | None = Query(None, max_length=100, description="ring id, member or reason"),
    sort: Literal["risk", "first_seen", "last_seen"] = "risk",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(50, ge=1, le=500),
    cursor: str | None = Query(None, description="next_cursor of the previous page"),
) -> Page[AlertSummary]:
    stmt = select(Alert)
    if status:
        stmt = stmt.where(Alert.status.in_(status))
    if ring_type:
        stmt = stmt.where(Alert.ring_type.in_(ring_type))
    if risk_min is not None:
        stmt = stmt.where(Alert.risk >= risk_min)
    if risk_max is not None:
        stmt = stmt.where(Alert.risk <= risk_max)
    if since is not None:
        stmt = stmt.where(Alert.first_seen_at >= since)
    if until is not None:
        stmt = stmt.where(Alert.first_seen_at <= until)
    if run_id:
        stmt = stmt.where(Alert.run_id == run_id)
    if assignee == "me":
        stmt = stmt.where(Alert.assignee_id == user.id)
    elif assignee == "none":
        stmt = stmt.where(Alert.assignee_id.is_(None))
    elif assignee:
        stmt = stmt.where(Alert.assignee_id == int(assignee))
    col = {"risk": Alert.risk, "first_seen": Alert.first_seen_at, "last_seen": Alert.last_seen_at}[
        sort
    ]
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Alert.id.desc())
    rows = list(db.scalars(stmt).all())
    # JSON-list and free-text filters are applied here (the queue is small).
    if detector:
        rows = [a for a in rows if detector in a.detectors]
    if q:
        needle = q.lower()
        rows = [
            a
            for a in rows
            if needle in a.alert_ref.lower()
            or needle in (a.reason or "").lower()
            or any(needle in m.lower() for m in a.members)
        ]
    start = int(cursor) if cursor and cursor.isdigit() else 0
    chunk = rows[start : start + limit]
    nxt = str(start + limit) if start + limit < len(rows) else None
    return Page[AlertSummary](
        items=[svc.summary(db, a) for a in chunk], next_cursor=nxt, total=len(rows)
    )


@router.get("/views", response_model=list[SavedViewOut], operation_id="alerts_views_list")
def views(db: DB, user: CurrentUser) -> list[SavedViewOut]:
    rows = db.scalars(
        select(SavedView).where(SavedView.user_id == user.id).order_by(SavedView.name)
    )
    return [SavedViewOut.model_validate(v) for v in rows]


@router.put("/views", response_model=SavedViewOut, operation_id="alerts_views_save")
def save_view(body: SavedViewIn, db: DB, user: CurrentUser) -> SavedViewOut:
    """Create or replace the caller's view with this name."""
    v = db.scalar(
        select(SavedView).where(SavedView.user_id == user.id, SavedView.name == body.name)
    )
    if v is None:
        v = SavedView(user_id=user.id, name=body.name, filters=body.filters)
        db.add(v)
    else:
        v.filters = body.filters
    db.commit()
    db.refresh(v)
    return SavedViewOut.model_validate(v)


@router.delete(
    "/views/{view_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    operation_id="alerts_views_delete",
    responses=NOT_FOUND,
)
def delete_view(view_id: int, db: DB, user: CurrentUser) -> Response:
    v = db.get(SavedView, view_id)
    if v is None or v.user_id != user.id:
        raise ApiError(404, "not_found", "No such saved view")
    db.delete(v)
    db.commit()
    return Response(status_code=204)


@router.post("/bulk", response_model=BulkResult, operation_id="alerts_bulk")
def bulk(body: BulkAlertAction, request: Request, db: DB, user: CurrentUser) -> BulkResult:
    """Assign or change the status of many alerts; each one is checked and audited."""
    if body.action == "status" and body.status is None:
        raise ApiError(422, "validation_error", "status is required for action=status")
    target = svc.assignee(db, body.assignee_id) if body.action == "assign" else None
    updated, rejected = [], []
    for alert_id in body.ids:
        a = db.get(Alert, alert_id)
        if a is None:
            rejected.append({"id": alert_id, "code": "not_found", "message": "not found"})
            continue
        try:
            if body.action == "status":
                assert body.status is not None
                check_alert(a.status, body.status, user.role == Role.ADMIN)
                before, a.status = a.status, body.status
                audit.record(
                    "ALERT_STATUS",
                    _who(user),
                    "alert",
                    str(a.id),
                    {
                        "from": before.value,
                        "to": body.status.value,
                        "bulk": True,
                        "ip": client_ip(request),
                    },
                    db,
                )
            else:
                a.assignee_id = target
                audit.record(
                    "ALERT_ASSIGNED",
                    _who(user),
                    "alert",
                    str(a.id),
                    {"assignee_id": target, "bulk": True, "ip": client_ip(request)},
                    db,
                )
            updated.append(a.id)
        except ApiError as e:
            rejected.append({"id": alert_id, "code": e.code, "message": e.message})
    db.commit()
    return BulkResult(updated=updated, rejected=rejected)


@router.get(
    "/{alert_id}", response_model=AlertDetail, operation_id="alerts_get", responses=NOT_FOUND
)
def alert(alert_id: int, db: DB) -> AlertDetail:
    a = svc.get_alert(db, alert_id)
    explanation = a.explanation
    live = state.live is not None and state.run_id == a.run_id
    ring = state.live.engine.tracker.rings.get(a.alert_ref) if live and state.live else None
    if ring is not None:  # fresher evidence straight from the engine
        explanation = ring_payload(ring)["explanation"] | {"threshold": a.threshold}
    labels = db.scalars(
        select(Label)
        .where(Label.run_id == a.run_id, Label.alert_ref == a.alert_ref)
        .order_by(Label.id)
    ).all()
    return AlertDetail(
        **svc.summary(db, a).model_dump(),
        members=list(a.members),
        explanation=explanation,
        history=list(a.history),
        labels=[
            LabelOut(
                id=lb.id,
                label=lb.label,
                author=svc.user_ref(db, lb.author_id),
                created_at=lb.created_at,
            )
            for lb in labels
        ],
        notes=svc.notes_for(db, run_id=a.run_id, alert_ref=a.alert_ref),
        live=ring is not None,
    )


@router.patch(
    "/{alert_id}",
    response_model=AlertSummary,
    operation_id="alerts_update",
    responses={**NOT_FOUND, **CONFLICT},
)
def update(
    alert_id: int, body: AlertUpdate, request: Request, db: DB, user: CurrentUser
) -> AlertSummary:
    a = svc.get_alert(db, alert_id)
    fields = body.model_fields_set
    if "status" in fields and body.status is not None and body.status != a.status:
        check_alert(a.status, body.status, user.role == Role.ADMIN)
        audit.record(
            "ALERT_STATUS",
            _who(user),
            "alert",
            str(a.id),
            {"from": a.status.value, "to": body.status.value, "ip": client_ip(request)},
            db,
        )
        a.status = body.status
    if "assignee_id" in fields:
        target = svc.assignee(db, body.assignee_id)
        if target != a.assignee_id:
            a.assignee_id = target
            audit.record(
                "ALERT_ASSIGNED",
                _who(user),
                "alert",
                str(a.id),
                {"assignee_id": target, "ip": client_ip(request)},
                db,
            )
    db.commit()
    return svc.summary(db, a)


@router.post(
    "/{alert_id}/labels",
    response_model=LabelResult,
    status_code=201,
    operation_id="alerts_label",
    responses=NOT_FOUND,
)
def label(alert_id: int, body: LabelIn, request: Request, db: DB, user: CurrentUser) -> LabelResult:
    """
    Analyst feedback. confirmed_fraud / dismissed_benign on a live run call the
    run's AlertPolicy.feedback (confirm / dismiss) and return the threshold change.
    """
    a = svc.get_alert(db, alert_id)
    row = Label(run_id=a.run_id, alert_ref=a.alert_ref, label=body.label, author_id=user.id)
    db.add(row)
    db.flush()
    adaptation: dict[str, Any] | None = None
    action = {LabelKind.CONFIRMED_FRAUD: "confirm", LabelKind.DISMISSED_BENIGN: "dismiss"}.get(
        body.label
    )
    live = state.live if state.live is not None and state.run_id == a.run_id else None
    if action and live is not None:
        risk = a.risk if a.risk is not None else 0.0
        adaptation = live.scoring.policy.feedback(a.alert_ref, a.ring_type, float(risk), action)
        live.record_feedback(a.alert_ref, action, adaptation, _who(user), body.note)
        message = "Feedback applied to the live run's alert policy."
    elif action:
        message = "The run is no longer live: the label is stored; no threshold changed."
    else:
        message = "Label stored."
    audit.record(
        "ALERT_LABELED",
        _who(user),
        "alert",
        str(a.id),
        {
            "label": body.label.value,
            "note": body.note,
            "threshold_adaptation": adaptation,
            "ip": client_ip(request),
        },
        db,
    )
    db.commit()
    return LabelResult(
        label=LabelOut(
            id=row.id, label=row.label, author=svc.user_ref(db, user.id), created_at=row.created_at
        ),
        threshold_adaptation=adaptation,
        message=message,
    )


@router.post(
    "/{alert_id}/notes",
    response_model=NoteOut,
    status_code=201,
    operation_id="alerts_add_note",
    responses=NOT_FOUND,
)
def add_note(alert_id: int, body: NoteIn, request: Request, db: DB, user: CurrentUser) -> NoteOut:
    a = svc.get_alert(db, alert_id)
    n = Note(run_id=a.run_id, alert_ref=a.alert_ref, author_id=user.id, body=body.body)
    db.add(n)
    db.flush()
    audit.record(
        "NOTE_ADDED",
        _who(user),
        "alert",
        str(a.id),
        {"note_id": n.id, "chars": len(body.body), "ip": client_ip(request)},
        db,
    )
    db.commit()
    return next(
        x for x in svc.notes_for(db, run_id=a.run_id, alert_ref=a.alert_ref) if x.id == n.id
    )
