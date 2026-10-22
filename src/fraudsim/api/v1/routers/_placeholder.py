"""Sub-routers whose features arrive in later Phase 2 milestones."""

from __future__ import annotations

from fastapi import APIRouter

from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope

# (router prefix, OpenAPI tag, milestone that implements it, admin only)
PLANNED = [
    ("alerts", "alerts", "P5", False),
    ("cases", "cases", "P5", False),
    ("entities", "entities", "P6", False),
    ("graph", "graph", "P6", False),
    ("reports", "reports", "P7", False),
    ("experiments", "experiments", "P8", False),
    ("rules", "rules", "P9", True),
    ("stream", "stream", "P3", False),
]


def planned_router(prefix: str, tag: str, milestone: str) -> APIRouter:
    router = APIRouter(prefix=f"/{prefix}", tags=[tag])

    @router.get(
        "",
        responses={
            501: {"model": ErrorEnvelope, "description": f"Arrives in milestone {milestone}"}
        },
        summary=f"{tag}: not implemented yet ({milestone})",
        operation_id=f"{tag}_index",
    )
    async def index() -> None:
        raise ApiError(
            501, "not_implemented", f"/api/v1/{prefix} is implemented in milestone {milestone}"
        )

    return router
