"""Investigation reports (P7)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from fraudsim.api.v1.schemas.cases import UserRef

Section = Literal[
    "executive_summary",
    "alert_table",
    "ring_detail",
    "contributions",
    "counterfactuals",
    "timeline",
    "notes",
    "sar_summary",
    "run_metrics",
    "limitations",
]


class ReportCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    run_ids: list[str] = Field(default_factory=list, max_length=20)
    alert_ids: list[int] = Field(default_factory=list, max_length=500)
    case_ids: list[int] = Field(default_factory=list, max_length=50)
    since: datetime | None = Field(
        None, description="Rings first seen at or after (simulated time)"
    )
    until: datetime | None = Field(
        None, description="Rings first seen at or before (simulated time)"
    )
    sections: list[Section] = Field(
        default_factory=lambda: [
            "executive_summary",
            "alert_table",
            "ring_detail",
            "contributions",
            "counterfactuals",
            "timeline",
            "notes",
            "sar_summary",
            "run_metrics",
            "limitations",
        ],
        min_length=1,
    )
    oracle: bool = Field(
        False, description='Add the "Oracle (simulator ground truth)" comparison per run'
    )
    format: Literal["html", "pdf"] = "html"


class ReportOut(BaseModel):
    id: str
    title: str
    format: Literal["html", "pdf"]
    scope: dict[str, object]
    run_ids: list[str]
    config_hashes: list[str]
    sha256: str = Field(description="SHA-256 of the report file")
    size_bytes: int
    created_by: UserRef | None
    created_at: datetime
    rings: int = Field(description="Rings in the report")
