"""Shared helpers for the alerts, cases and audit routers (P5)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from fraudsim.api.v1.auth import audit
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas.cases import AlertSummary, NoteOut, UserRef
from fraudsim.appdb.models import Alert, CaseAlert, Label, Note, User


def user_ref(db: Session, user_id: int | None) -> UserRef | None:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    return UserRef(id=u.id, email=u.email, display_name=u.display_name) if u else None


def assignee(db: Session, assignee_id: int | None) -> int | None:
    """0 means unassign; anything else must be an active user."""
    if assignee_id is None or assignee_id == 0:
        return None
    u = db.get(User, assignee_id)
    if u is None or not u.is_active:
        raise ApiError(422, "validation_error", f"No active user with id {assignee_id}")
    return u.id


def get_alert(db: Session, alert_id: int) -> Alert:
    a = db.get(Alert, alert_id)
    if a is None:
        raise ApiError(404, "not_found", f"Alert {alert_id} not found")
    return a


def latest_label(db: Session, a: Alert) -> Label | None:
    return db.scalar(
        select(Label)
        .where(Label.run_id == a.run_id, Label.alert_ref == a.alert_ref)
        .order_by(Label.id.desc())
    )


def summary(db: Session, a: Alert) -> AlertSummary:
    lab = latest_label(db, a)
    case_ids = db.scalars(
        select(CaseAlert.case_id).where(
            CaseAlert.run_id == a.run_id, CaseAlert.alert_ref == a.alert_ref
        )
    ).all()
    return AlertSummary(
        id=a.id,
        run_id=a.run_id,
        alert_ref=a.alert_ref,
        kind=a.kind,
        status=a.status,
        assignee=user_ref(db, a.assignee_id),
        ring_type=a.ring_type,
        ring_status=a.ring_status,
        risk=a.risk,
        threshold=a.threshold,
        calibration_bucket=a.calibration_bucket,
        members_count=len(a.members),
        detectors=list(a.detectors),
        reason=a.reason,
        first_seen_at=a.first_seen_at,
        last_seen_at=a.last_seen_at,
        sim_time_s=a.sim_time_s,
        latest_label=lab.label if lab else None,
        case_ids=sorted(set(case_ids)),
    )


def notes_for(db: Session, **where: Any) -> list[NoteOut]:
    """Current notes (latest version of each), with earlier versions as revisions."""
    rows = db.scalars(select(Note).filter_by(**where).order_by(Note.id)).all()
    superseded = {n.supersedes_id for n in rows if n.supersedes_id is not None}
    by_id = {n.id: n for n in rows}
    out = []
    for n in rows:
        if n.id in superseded:
            continue
        chain, prev = [], n.supersedes_id
        while prev is not None and prev in by_id:
            old = by_id[prev]
            author = user_ref(db, old.author_id)
            chain.append(
                {
                    "body": old.body,
                    "author": author.model_dump() if author else None,
                    "created_at": old.created_at.isoformat(),
                }
            )
            prev = old.supersedes_id
        out.append(
            NoteOut(
                id=n.id,
                body=n.body,
                author=user_ref(db, n.author_id),
                created_at=n.created_at,
                edited=n.supersedes_id is not None,
                revisions=list(reversed(chain)),
            )
        )
    return out


def evidence_snapshot(a: Alert) -> tuple[dict[str, Any], str]:
    """Frozen JSON copy of the alert's evidence (canonical JSON) and its SHA-256."""
    snap = {
        "run_id": a.run_id,
        "alert_ref": a.alert_ref,
        "ring_type": a.ring_type,
        "risk": a.risk,
        "threshold": a.threshold,
        "members": list(a.members),
        "detectors": list(a.detectors),
        "reason": a.reason,
        "evidence_subgraph": (a.explanation or {}).get("evidence_subgraph"),
        "last_seen_at": a.last_seen_at.isoformat(),
    }
    blob = json.dumps(snap, sort_keys=True, separators=(",", ":"), default=str)
    return snap, hashlib.sha256(blob.encode()).hexdigest()


def history_of(object_type: str, object_id: str) -> list[dict[str, Any]]:
    """App audit entries about one object, oldest first."""
    key = f"{object_type}:{object_id}"
    return [
        {
            "seq": e.seq,
            "ts": e.ts,
            "action_type": e.action_type,
            "actor": e.actor,
            "details": e.details,
        }
        for e in audit.trail().read_entries()
        if e.ring_id == key
    ]
