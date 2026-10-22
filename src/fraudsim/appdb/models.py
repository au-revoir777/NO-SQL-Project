"""
Relational app state for the web application (Phase 2): users, cases and their
alerts, notes, labels, versioned rule sets, generated reports, and references
from these objects to entries in the hash-chained audit trail.

ASSUMPTION (phase2_prompt.md): analyst work lives here, not in Neo4j, so TTL
pruning of the detection graph can never delete it and tests run without services.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class Role(enum.StrEnum):
    ANALYST = "analyst"
    ADMIN = "admin"


class CaseStatus(enum.StrEnum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Priority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LabelKind(enum.StrEnum):
    CONFIRMED_FRAUD = "confirmed_fraud"
    DISMISSED_BENIGN = "dismissed_benign"
    NEEDS_INFO = "needs_info"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    # Stored as plain strings (portable across SQLite and Postgres).
    return Enum(e, name=name, native_enum=False, values_callable=lambda x: [m.value for m in x])


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), default=Role.ANALYST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[CaseStatus] = mapped_column(
        _enum(CaseStatus, "case_status"), default=CaseStatus.OPEN
    )
    priority: Mapped[Priority] = mapped_column(_enum(Priority, "priority"), default=Priority.MEDIUM)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    alerts: Mapped[list[CaseAlert]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseAlert(Base):
    """An alert (a tracked ring in a given run) attached to a case."""

    __tablename__ = "case_alerts"
    __table_args__ = (UniqueConstraint("case_id", "run_id", "alert_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(String(64))
    alert_ref: Mapped[str] = mapped_column(String(64))  # tracker ring id, e.g. R000012
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case: Mapped[Case] = relationship(back_populates="alerts")


class Note(Base):
    """Markdown note on a case or an alert. Edits create a new row that supersedes the old."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alert_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    alert_ref: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[LabelKind] = mapped_column(_enum(LabelKind, "label_kind"))
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RuleSet(Base):
    __tablename__ = "rule_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True)
    params: Mapped[dict[str, Any]] = mapped_column()
    config_hash: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    scope: Mapped[dict[str, Any]] = mapped_column()
    run_ids: Mapped[list[Any]] = mapped_column()
    config_hashes: Mapped[list[Any]] = mapped_column()
    format: Mapped[str] = mapped_column(String(10))  # html | pdf
    path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditRef(Base):
    """Links an app object to an entry of the hash-chained audit trail (logging/audit.py)."""

    __tablename__ = "audit_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_run_id: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str] = mapped_column(String(32))
    object_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
