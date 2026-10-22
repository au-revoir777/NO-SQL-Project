"""GET /api/v1/health: liveness of the API and the state of its dependencies."""

from __future__ import annotations

import os

from fastapi import APIRouter

from fraudsim import appdb
from fraudsim.api.state import state
from fraudsim.api.v1.schemas import ComponentHealth, HealthV1

VERSION = "0.2.0"
router = APIRouter(tags=["system"])


def _redis_health() -> ComponentHealth:
    url = os.environ.get("REDIS_URL")
    if not url:
        return ComponentHealth(name="redis", status="not_configured")
    try:
        import redis

        ok = bool(redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5).ping())
    except Exception as exc:  # unreachable, or the redis extra is not installed
        return ComponentHealth(name="redis", status="unavailable", detail=type(exc).__name__)
    return ComponentHealth(name="redis", status="ok" if ok else "unavailable")


@router.get("/health", response_model=HealthV1, operation_id="health")
async def health() -> HealthV1:
    components = [ComponentHealth(name="api", status="ok")]

    db_ok = appdb.ping()
    revision = appdb.current_revision() if db_ok else None
    components.append(
        ComponentHealth(
            name="app_db",
            status="ok" if db_ok and revision else "unavailable",
            detail=None
            if revision
            else ("not migrated: run `fraudsim db-upgrade`" if db_ok else "unreachable"),
        )
    )

    if state.neo4j_client is None:
        components.append(ComponentHealth(name="neo4j", status="not_configured"))
    else:
        try:
            ok = bool(state.neo4j_client.verify_connectivity())
        except Exception:
            ok = False
        components.append(ComponentHealth(name="neo4j", status="ok" if ok else "unavailable"))

    components.append(_redis_health())
    degraded = any(c.status == "unavailable" for c in components)
    return HealthV1(
        status="degraded" if degraded else "ok",
        version=VERSION,
        components=components,
        db_revision=revision,
    )
