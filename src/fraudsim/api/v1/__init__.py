"""
Versioned API for the Phase 2 web application, mounted at /api/v1.

The pre-existing routes (/health, /runs/*, /ws, /ui, ...) are untouched; the new
web app talks only to /api/v1. See docs/webapp.md for the contract.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from fraudsim.api.v1 import errors
from fraudsim.api.v1.routers import runs, system
from fraudsim.api.v1.routers._placeholder import PLANNED, planned_router
from fraudsim.api.v1.schemas import ErrorEnvelope

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    422: {"model": ErrorEnvelope, "description": "Validation error"},
    500: {"model": ErrorEnvelope, "description": "Internal error"},
}


def build_router() -> APIRouter:
    router = APIRouter(prefix=errors.V1_PREFIX, responses=ERROR_RESPONSES)
    router.include_router(system.router)
    router.include_router(runs.router)
    for prefix, tag, milestone in PLANNED:
        router.include_router(planned_router(prefix, tag, milestone))
    return router


def install(app: FastAPI) -> None:
    errors.install(app)
    app.include_router(build_router())
