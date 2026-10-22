"""
Versioned API for the Phase 2 web application, mounted at /api/v1.

The pre-existing routes (/health, /runs/*, /ws, /ui, ...) are untouched; the new
web app talks only to /api/v1. See docs/webapp.md for the contract.

Access control (server-side, on every request):
- public: GET /health, GET /auth/csrf, POST /auth/login, POST /auth/refresh
- analyst or admin: everything else
- admin only: /admin/*, /rules/*
State-changing requests also need the CSRF double-submit header.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, FastAPI

from fraudsim import appdb
from fraudsim.api.v1 import errors
from fraudsim.api.v1.auth.deps import csrf_protect, require_admin, require_user
from fraudsim.api.v1.routers import admin, auth, runs, system
from fraudsim.api.v1.routers._placeholder import PLANNED, planned_router
from fraudsim.api.v1.schemas import ErrorEnvelope

logger = structlog.get_logger(__name__)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorEnvelope, "description": "Validation error"},
    500: {"model": ErrorEnvelope, "description": "Internal error"},
}
AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Not signed in or session invalid"},
    403: {"model": ErrorEnvelope, "description": "Role or CSRF check failed"},
}
ANALYST = [Depends(require_user), Depends(csrf_protect)]
ADMIN = [Depends(require_admin), Depends(csrf_protect)]


def build_router() -> APIRouter:
    router = APIRouter(prefix=errors.V1_PREFIX, responses=ERROR_RESPONSES)
    router.include_router(system.router)
    router.include_router(auth.router)
    router.include_router(runs.router, dependencies=ANALYST, responses=AUTH_RESPONSES)
    router.include_router(admin.router, dependencies=ADMIN, responses=AUTH_RESPONSES)
    for prefix, tag, milestone, admin_only in PLANNED:
        router.include_router(
            planned_router(prefix, tag, milestone),
            dependencies=ADMIN if admin_only else ANALYST,
            responses=AUTH_RESPONSES,
        )
    return router


def seed_on_startup() -> None:
    """Create demo users from DEMO_* env vars, if the app DB is migrated."""
    from fraudsim.api.v1.auth.users import seed_demo_users

    if not appdb.ping() or appdb.current_revision() is None:
        return
    try:
        db = appdb.open_session()
        try:
            seed_demo_users(db)
        finally:
            db.close()
    except Exception as exc:  # never block start-up on seeding
        logger.warning("demo user seeding failed", error=str(exc))


def install(app: FastAPI) -> None:
    errors.install(app)
    app.include_router(build_router())
    app.add_event_handler("startup", seed_on_startup)
