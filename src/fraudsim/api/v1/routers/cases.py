"""
/api/v1/cases, /api/v1/notes, /api/v1/users and /api/v1/audit (P5).

Cases group alerts. Attaching an alert freezes a JSON copy of its evidence
(canonical JSON) and writes its SHA-256 into the audit trail, so a later
change to the alert cannot silently change what the case was based on. Notes
are Markdown; editing one adds a new version and keeps the old one. The audit
view (admin) reads the hash-chained app trail and verifies it.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.auth.deps import DB, CurrentUser, client_ip, require_admin
from fraudsim.api.v1.cases import service as svc
from fraudsim.api.v1.cases.workflow import check_case
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope, Page
from fraudsim.api.v1.schemas.cases import (
    AuditEntryOut,
    AuditVerify,
    CaseAlertOut,
    CaseAttach,
    CaseCreate,
    CaseDetail,
    CaseSummary,
    CaseUpdate,
    NoteIn,
    NoteOut,
    SnapshotOut,
    UserRef,
)
from fraudsim.appdb.models import Case, CaseAlert, CaseStatus, Note, Role, User

router = APIRouter(tags=["cases"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Not found"}
}


def _who(user: Any) -> str:
    return str(user.email)


def _case(db: Session, case_id: int) -> Case:
    c = db.get(Case, case_id)
    if c is None:
        raise ApiError(404, "not_found", f"Case {case_id} not found")
    return c


def _summary(db: Any, c: Case) -> CaseSummary:
    return CaseSummary(
        id=c.id,
        title=c.title,
        status=c.status,
        priority=c.priority,
        resolution=c.resolution,
        assignee=svc.user_ref(db, c.assignee_id),
        created_by=svc.user_ref(db, c.created_by_id),
        alerts_count=len(c.alerts),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _attach(db: Any, c: Case, alert_ids: list[int], user: Any, request: Request) -> None:
    have = {(ca.run_id, ca.alert_ref) for ca in c.alerts}
    for alert_id in alert_ids:
        a = svc.get_alert(db, alert_id)
        if (a.run_id, a.alert_ref) in have:
            continue
        snap, digest = svc.evidence_snapshot(a)
        c.alerts.append(
            CaseAlert(
                run_id=a.run_id,
                alert_ref=a.alert_ref,
                evidence_snapshot=snap,
                snapshot_sha256=digest,
            )
        )
        have.add((a.run_id, a.alert_ref))
        audit.record(
            "CASE_ALERT_ATTACHED",
            _who(user),
            "case",
            str(c.id),
            {
                "alert_id": a.id,
                "run_id": a.run_id,
                "alert_ref": a.alert_ref,
                "snapshot_sha256": digest,
                "ip": client_ip(request),
            },
            db,
        )


@router.get("/cases", response_model=Page[CaseSummary], operation_id="cases_list")
def cases(
    db: DB,
    user: CurrentUser,
    status: Annotated[list[CaseStatus] | None, Query()] = None,
    assignee: str | None = Query(None, description="me | none | <user id>"),
    limit: int = Query(50, ge=1, le=500),
    cursor: str | None = None,
) -> Page[CaseSummary]:
    stmt = select(Case)
    if status:
        stmt = stmt.where(Case.status.in_(status))
    if assignee == "me":
        stmt = stmt.where(Case.assignee_id == user.id)
    elif assignee == "none":
        stmt = stmt.where(Case.assignee_id.is_(None))
    elif assignee:
        stmt = stmt.where(Case.assignee_id == int(assignee))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    start = int(cursor) if cursor and cursor.isdigit() else 0
    rows = db.scalars(
        stmt.order_by(Case.updated_at.desc(), Case.id.desc()).offset(start).limit(limit)
    )
    nxt = str(start + limit) if start + limit < total else None
    return Page[CaseSummary](items=[_summary(db, c) for c in rows], next_cursor=nxt, total=total)


@router.post("/cases", response_model=CaseDetail, status_code=201, operation_id="cases_create")
def create(body: CaseCreate, request: Request, db: DB, user: CurrentUser) -> CaseDetail:
    c = Case(
        title=body.title,
        priority=body.priority,
        created_by_id=user.id,
        assignee_id=svc.assignee(db, body.assignee_id),
        status=CaseStatus.OPEN,
    )
    db.add(c)
    db.flush()
    audit.record(
        "CASE_CREATED",
        _who(user),
        "case",
        str(c.id),
        {
            "title": body.title,
            "priority": body.priority.value,
            "alert_ids": body.alert_ids,
            "ip": client_ip(request),
        },
        db,
    )
    _attach(db, c, body.alert_ids, user, request)
    db.commit()
    return detail(c.id, db)


@router.get(
    "/cases/{case_id}", response_model=CaseDetail, operation_id="cases_get", responses=NOT_FOUND
)
def detail(case_id: int, db: DB) -> CaseDetail:
    from fraudsim.appdb.models import Alert

    c = _case(db, case_id)
    linked = []
    for ca in c.alerts:
        a = db.scalar(
            select(Alert).where(Alert.run_id == ca.run_id, Alert.alert_ref == ca.alert_ref)
        )
        if a is not None:
            linked.append(
                CaseAlertOut(
                    alert=svc.summary(db, a),
                    snapshot_sha256=ca.snapshot_sha256,
                    added_at=ca.added_at,
                )
            )
    return CaseDetail(
        **_summary(db, c).model_dump(),
        alerts=linked,
        notes=svc.notes_for(db, case_id=c.id),
        history=svc.history_of("case", str(c.id)),
    )


@router.patch(
    "/cases/{case_id}",
    response_model=CaseDetail,
    operation_id="cases_update",
    responses={**NOT_FOUND, 409: {"model": ErrorEnvelope, "description": "Transition not allowed"}},
)
def update(
    case_id: int, body: CaseUpdate, request: Request, db: DB, user: CurrentUser
) -> CaseDetail:
    c = _case(db, case_id)
    fields = body.model_fields_set
    changes: dict[str, Any] = {}
    if "status" in fields and body.status is not None and body.status != c.status:
        resolution = body.resolution if "resolution" in fields else c.resolution
        check_case(c.status, body.status, user.role == Role.ADMIN, resolution)
        changes["status"] = {"from": c.status.value, "to": body.status.value}
        c.status = body.status
    if "resolution" in fields and body.resolution != c.resolution:
        c.resolution = body.resolution
        changes["resolution"] = body.resolution
    if "title" in fields and body.title and body.title != c.title:
        c.title = body.title
        changes["title"] = body.title
    if "priority" in fields and body.priority is not None and body.priority != c.priority:
        changes["priority"] = {"from": c.priority.value, "to": body.priority.value}
        c.priority = body.priority
    if "assignee_id" in fields:
        target = svc.assignee(db, body.assignee_id)
        if target != c.assignee_id:
            c.assignee_id = target
            changes["assignee_id"] = target
    if changes:
        audit.record(
            "CASE_UPDATED",
            _who(user),
            "case",
            str(c.id),
            {"changes": changes, "ip": client_ip(request)},
            db,
        )
    db.commit()
    return detail(c.id, db)


@router.post(
    "/cases/{case_id}/alerts",
    response_model=CaseDetail,
    operation_id="cases_attach",
    responses=NOT_FOUND,
)
def attach(
    case_id: int, body: CaseAttach, request: Request, db: DB, user: CurrentUser
) -> CaseDetail:
    c = _case(db, case_id)
    if c.status == CaseStatus.CLOSED:
        raise ApiError(409, "invalid_transition", "A closed case cannot take new alerts")
    _attach(db, c, body.alert_ids, user, request)
    db.commit()
    return detail(c.id, db)


@router.get(
    "/cases/{case_id}/alerts/{alert_id}/snapshot",
    response_model=SnapshotOut,
    operation_id="cases_snapshot",
    responses=NOT_FOUND,
)
def snapshot(case_id: int, alert_id: int, db: DB) -> SnapshotOut:
    """The frozen evidence attached to the case (its hash is in the audit trail)."""
    c = _case(db, case_id)
    a = svc.get_alert(db, alert_id)
    ca = next((x for x in c.alerts if (x.run_id, x.alert_ref) == (a.run_id, a.alert_ref)), None)
    if ca is None or ca.evidence_snapshot is None:
        raise ApiError(404, "not_found", "This alert is not attached to the case")
    return SnapshotOut(
        alert_id=a.id, sha256=ca.snapshot_sha256 or "", snapshot=ca.evidence_snapshot
    )


@router.post(
    "/cases/{case_id}/notes",
    response_model=NoteOut,
    status_code=201,
    operation_id="cases_add_note",
    responses=NOT_FOUND,
)
def add_note(case_id: int, body: NoteIn, request: Request, db: DB, user: CurrentUser) -> NoteOut:
    c = _case(db, case_id)
    n = Note(case_id=c.id, author_id=user.id, body=body.body)
    db.add(n)
    db.flush()
    audit.record(
        "NOTE_ADDED",
        _who(user),
        "case",
        str(c.id),
        {"note_id": n.id, "chars": len(body.body), "ip": client_ip(request)},
        db,
    )
    db.commit()
    return next(x for x in svc.notes_for(db, case_id=c.id) if x.id == n.id)


@router.patch(
    "/notes/{note_id}",
    response_model=NoteOut,
    operation_id="notes_edit",
    responses={**NOT_FOUND, 403: {"model": ErrorEnvelope, "description": "Not the author"}},
)
def edit_note(note_id: int, body: NoteIn, request: Request, db: DB, user: CurrentUser) -> NoteOut:
    """Edit a note: a new version replaces it; the old version stays in the history."""
    old = db.get(Note, note_id)
    if old is None:
        raise ApiError(404, "not_found", f"Note {note_id} not found")
    if db.scalar(select(Note).where(Note.supersedes_id == note_id)) is not None:
        raise ApiError(409, "conflict", "This version was already edited; edit the latest one")
    if old.author_id != user.id and user.role != Role.ADMIN:
        raise ApiError(403, "forbidden", "Only the author or an admin can edit a note")
    new = Note(
        case_id=old.case_id,
        run_id=old.run_id,
        alert_ref=old.alert_ref,
        author_id=user.id,
        body=body.body,
        supersedes_id=old.id,
    )
    db.add(new)
    db.flush()
    obj = (
        ("case", str(old.case_id))
        if old.case_id
        else ("alert_ref", f"{old.run_id}/{old.alert_ref}")
    )
    audit.record(
        "NOTE_EDITED",
        _who(user),
        obj[0],
        obj[1],
        {"note_id": new.id, "supersedes": old.id, "ip": client_ip(request)},
        db,
    )
    db.commit()
    where: dict[str, Any] = (
        {"case_id": old.case_id}
        if old.case_id
        else {"run_id": old.run_id, "alert_ref": old.alert_ref}
    )
    return next(x for x in svc.notes_for(db, **where) if x.id == new.id)


@router.get("/users", response_model=list[UserRef], operation_id="users_assignable")
def assignable(db: DB) -> list[UserRef]:
    """Active users, for assignee pickers."""
    rows = db.scalars(select(User).where(User.is_active).order_by(User.display_name, User.email))
    return [UserRef(id=u.id, email=u.email, display_name=u.display_name) for u in rows]


@router.get(
    "/audit",
    response_model=Page[AuditEntryOut],
    operation_id="audit_list",
    dependencies=[Depends(require_admin)],
)
def audit_entries(
    action: str | None = None,
    actor: str | None = None,
    object: str | None = Query(None, description="e.g. case:3 or alert:12"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: str | None = None,
) -> Page[AuditEntryOut]:
    """Admin: the app audit trail, newest first."""
    rows = list(reversed(audit.trail().read_entries()))
    if action:
        rows = [e for e in rows if e.action_type == action]
    if actor:
        rows = [e for e in rows if e.actor == actor]
    if object:
        rows = [e for e in rows if e.ring_id == object]
    start = int(cursor) if cursor and cursor.isdigit() else 0
    chunk = rows[start : start + limit]
    return Page[AuditEntryOut](
        items=[
            AuditEntryOut(
                seq=e.seq,
                ts=e.ts,
                action_type=e.action_type,
                actor=e.actor,
                object=e.ring_id,
                details=e.details,
                hash=e.hash,
            )
            for e in chunk
        ],
        next_cursor=str(start + limit) if start + limit < len(rows) else None,
        total=len(rows),
    )


@router.get(
    "/audit/verify",
    response_model=AuditVerify,
    operation_id="audit_verify",
    dependencies=[Depends(require_admin)],
)
def audit_verify() -> AuditVerify:
    """Admin: check the hash chain (as `fraudsim audit-verify`)."""
    ok, problem = audit.trail().verify()
    return AuditVerify(ok=ok, entries=len(audit.trail().read_entries()), problem=problem)
