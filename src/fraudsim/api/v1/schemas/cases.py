"""Alerts, cases, notes, labels, saved views and the audit view (P5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fraudsim.appdb.models import AlertStatus, CaseStatus, LabelKind, Priority


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    display_name: str


class AlertSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: str
    alert_ref: str
    kind: str
    status: AlertStatus
    assignee: UserRef | None
    ring_type: str
    ring_status: str
    risk: float | None
    threshold: float | None
    calibration_bucket: str | None
    members_count: int
    detectors: list[str]
    reason: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    sim_time_s: float
    latest_label: LabelKind | None = None
    case_ids: list[int] = Field(default_factory=list)


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: LabelKind
    author: UserRef | None
    created_at: datetime


class NoteOut(BaseModel):
    id: int
    body: str
    author: UserRef | None
    created_at: datetime
    edited: bool = Field(description="True when this note replaced an earlier version")
    revisions: list[dict[str, Any]] = Field(
        default_factory=list, description="Earlier versions (oldest first): body, author, time"
    )


class AlertDetail(AlertSummary):
    members: list[str]
    explanation: dict[str, Any] | None
    history: list[dict[str, Any]]
    labels: list[LabelOut]
    notes: list[NoteOut]
    live: bool = Field(description="The run is still live; evidence is refreshed from the engine")
    activity: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Audit entries of this alert (status, assignment, labels, notes), oldest first",
    )


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    assignee_id: int | None = Field(default=None, description="0 unassigns")


class BulkAlertAction(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["assign", "status"]
    assignee_id: int | None = Field(default=None, description="For assign; 0 unassigns")
    status: AlertStatus | None = None


class BulkResult(BaseModel):
    updated: list[int]
    rejected: list[dict[str, Any]] = Field(description="id, code and message per rejected alert")


class LabelIn(BaseModel):
    label: LabelKind
    note: str = Field(default="", max_length=2000)


class LabelResult(BaseModel):
    label: LabelOut
    threshold_adaptation: dict[str, Any] | None = Field(
        description="AlertPolicy.feedback result (confirm/dismiss on a live run), else null"
    )
    message: str


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000, description="Markdown")


class SavedViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    filters: dict[str, Any]


class SavedViewOut(SavedViewIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    alert_ids: list[int] = Field(min_length=1, max_length=200)
    priority: Priority = Priority.MEDIUM
    assignee_id: int | None = None


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    status: CaseStatus | None = None
    priority: Priority | None = None
    assignee_id: int | None = Field(default=None, description="0 unassigns")
    resolution: str | None = Field(default=None, max_length=5000)


class CaseAttach(BaseModel):
    alert_ids: list[int] = Field(min_length=1, max_length=200)


class CaseAlertOut(BaseModel):
    alert: AlertSummary
    snapshot_sha256: str | None = Field(description="SHA-256 of the frozen evidence snapshot")
    added_at: datetime


class CaseSummary(BaseModel):
    id: int
    title: str
    status: CaseStatus
    priority: Priority
    resolution: str | None
    assignee: UserRef | None
    created_by: UserRef | None
    alerts_count: int
    created_at: datetime
    updated_at: datetime


class CaseDetail(CaseSummary):
    alerts: list[CaseAlertOut]
    notes: list[NoteOut]
    history: list[dict[str, Any]] = Field(description="Audit entries of this case, oldest first")


class SnapshotOut(BaseModel):
    alert_id: int
    sha256: str
    snapshot: dict[str, Any]


class AuditEntryOut(BaseModel):
    seq: int
    ts: str
    action_type: str
    actor: str
    object: str = Field(description="object_type:object_id")
    details: dict[str, Any]
    hash: str


class AuditVerify(BaseModel):
    ok: bool
    entries: int
    problem: str | None


class WhatIfIn(BaseModel):
    changes: dict[str, float] = Field(
        default_factory=dict,
        description="Actionable feature -> new value; the other features keep their scored values",
    )


class WhatIfFeature(BaseModel):
    name: str
    label: str
    value: float
    original: float
    actionable: bool
    contribution: float


class WhatIfCounterfactual(BaseModel):
    feature: str
    label: str
    current: float
    target: float
    valid: bool = Field(description="Setting the feature to target scores below the threshold")


class WhatIfModel(BaseModel):
    path: str
    sha256: str | None
    from_run: bool = Field(description="The run's own scorer (else the shipped model)")


class WhatIfOut(BaseModel):
    model: WhatIfModel
    threshold: float
    original_score: float = Field(description="Calibrated score of the scored vector, unmodified")
    score: float = Field(description="Calibrated score with the changes")
    raw: float = Field(description="Model probability before calibration, with the changes")
    alert: bool = Field(description="score >= threshold")
    flips: bool = Field(description="The changes move the decision across the threshold")
    features: list[WhatIfFeature]
    counterfactuals: list[WhatIfCounterfactual]
