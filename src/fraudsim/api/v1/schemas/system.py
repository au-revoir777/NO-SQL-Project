"""Schemas for /api/v1 system and run-status routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    name: Literal["api", "app_db", "neo4j", "redis"]
    status: Literal["ok", "unavailable", "not_configured"]
    detail: str | None = None


class HealthV1(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    api_version: Literal["v1"] = "v1"
    components: list[ComponentHealth]
    db_revision: str | None = Field(
        default=None, description="Alembic revision of the app-state store"
    )


class RunStatusV1(BaseModel):
    """The live run, read from the existing engine (same data as GET /status)."""

    run_id: str
    status: str
    scenario: str
    seed: int
    events_emitted: int
    rings_tracked: int
    sim_time_s: float
    speed_multiplier: float
