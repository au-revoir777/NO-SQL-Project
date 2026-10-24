"""
/api/v1/entities and /api/v1/graph: search, entity pages, bounded k-hop
neighbourhoods and the ring view (P6). The walk itself is
`fraudsim.graph.explore.Explorer`.

Sources:
- run: the current run's graph store (the engine's in-memory store);
- course: the course seed graph (`seed.py`, replayed through the event
  generator into an in-memory store, built once);
- neo4j: the configured Neo4j database (for example the graph `seed.py`
  loads), read with the same primitives in Cypher.

Handlers for in-memory sources are async on purpose: they run on the event
loop, between engine batches, so they never read the store while the engine
writes it. Neo4j reads go to the threadpool.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from fraudsim import appdb
from fraudsim.api.state import state
from fraudsim.api.v1.errors import ApiError
from fraudsim.api.v1.schemas import ErrorEnvelope
from fraudsim.api.v1.schemas.explorer import (
    EntityAlert,
    EntityDetail,
    EntityHit,
    EntityRing,
    Kind,
    NeighbourhoodOut,
    Rel,
    RingMembership,
    RingViewOut,
    Source,
)
from fraudsim.appdb.models import Alert
from fraudsim.detectors.engine import EngineConfig
from fraudsim.graph.explore import KINDS, RELS, Explorer, MemoryReads, Neo4jReads, Window
from fraudsim.graph.store import InMemoryGraphStore

entities = APIRouter(prefix="/entities", tags=["entities"])
graph = APIRouter(prefix="/graph", tags=["graph"])

ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorEnvelope, "description": "Unknown entity or ring"},
    409: {"model": ErrorEnvelope, "description": "The source is not available"},
}
MAX_NODES = 1000


@lru_cache(maxsize=1)
def course_store() -> InMemoryGraphStore:
    """The course seed graph (seed.py, random seed 42) as an in-memory store."""
    from fraudsim.simulator.event_generator import EventGenerator

    store = InMemoryGraphStore()
    store.apply(EventGenerator(seed=42, run_id="course").generate_seed_events())
    return store


def _caps(source: Source) -> EngineConfig:
    if source == "run" and state.live is not None:
        cfg: EngineConfig = state.live.engine.cfg
        return cfg
    return EngineConfig()


def _explorer(source: Source) -> Explorer:
    if source == "course":
        return Explorer(MemoryReads(course_store()))
    if source == "neo4j":
        if state.neo4j_client is None:
            raise ApiError(409, "source_unavailable", "Neo4j is not configured for this API")
        return Explorer(Neo4jReads(state.neo4j_client))
    if state.live is None:
        raise ApiError(409, "no_run", "No current run: start one, or explore the course graph")
    return Explorer(MemoryReads(state.live.engine.store))


async def _call(source: Source, fn: Any, *args: Any, **kwargs: Any) -> Any:
    if source == "neo4j":
        return await run_in_threadpool(fn, *args, **kwargs)
    return fn(*args, **kwargs)


def _parse_seed(seed: str) -> tuple[str, str]:
    kind, _, ident = seed.partition(":")
    if kind not in KINDS or not ident:
        raise ApiError(
            422,
            "validation_error",
            f"seed must be kind:id with kind one of {', '.join(KINDS)} (got {seed!r})",
        )
    return kind, ident


# ─── Entities ─────────────────────────────────────────────────────────


@entities.get("/search", response_model=list[EntityHit], operation_id="entities_search")
async def search(
    q: Annotated[str, Query(min_length=1, max_length=64, description="Id prefix")],
    kind: Annotated[list[Kind] | None, Query(description="Limit to these kinds")] = None,
    source: Source = "run",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[EntityHit]:
    ex = _explorer(source)
    kinds = tuple(kind) if kind else KINDS
    hits = await _call(source, ex.search, q, kinds, limit)
    return [EntityHit.model_validate(h) for h in hits]


def _linked_alerts(kind: str, entity_id: str, users: set[str]) -> list[EntityAlert]:
    """App-DB alerts of the current run whose members include the user (or, for an
    attribute, at least two of its users)."""
    if state.run_id is None or not appdb.ping():
        return []
    db = appdb.open_session()
    try:
        rows = db.scalars(select(Alert).where(Alert.run_id == state.run_id)).all()
    finally:
        db.close()
    need = 1 if kind == "user" else 2
    return [
        EntityAlert(
            id=a.id,
            alert_ref=a.alert_ref,
            status=a.status.value,
            risk=a.risk,
            ring_type=a.ring_type,
        )
        for a in rows
        if len(users & set(a.members)) >= need
    ]


def _linked_rings(kind: str, users: set[str]) -> list[EntityRing]:
    if state.live is None:
        return []
    need = 1 if kind == "user" else 2
    return [
        EntityRing(
            ring_id=r.ring_id,
            status=r.status.value,
            ring_type=r.ring_type.value,
            members=len(r.members),
            risk=r.risk,
        )
        for r in sorted(state.live.engine.tracker.rings.values(), key=lambda r: r.ring_id)
        if len(users & r.members) >= need
    ]


@entities.get(
    "/{kind}/{entity_id}",
    response_model=EntityDetail,
    operation_id="entities_get",
    responses=ERRORS,
)
async def entity(kind: Kind, entity_id: str, source: Source = "run") -> EntityDetail:
    ex = _explorer(source)
    detail = await _call(source, ex.entity, kind, entity_id)
    if detail is None:
        raise ApiError(404, "not_found", f"No {kind} {entity_id!r} in the {source} graph")
    users = {entity_id} if kind == "user" else {u["id"] for u in detail["users"]}
    out = EntityDetail(source=source, **detail)
    if kind != "user":
        out.is_hub = detail["degree"] > _caps(source).far_fanout
    if source == "run":
        out.alerts = await run_in_threadpool(_linked_alerts, kind, entity_id, users)
        out.rings = _linked_rings(kind, users)
    return out


# ─── Graph ────────────────────────────────────────────────────────────


@graph.get(
    "/neighbourhood",
    response_model=NeighbourhoodOut,
    operation_id="graph_neighbourhood",
    responses=ERRORS,
)
async def neighbourhood(
    seed: Annotated[
        list[str], Query(min_length=1, max_length=2, description="kind:id, e.g. device:device_007")
    ],
    k: Annotated[int, Query(ge=0, le=3, description="User hops")] = 1,
    source: Source = "run",
    rel: Annotated[list[Rel] | None, Query(description="Relationship types to follow")] = None,
    since_t: float | None = None,
    until_t: float | None = None,
    max_fanout: Annotated[int | None, Query(ge=1, le=10_000)] = None,
    far_fanout: Annotated[int | None, Query(ge=1, le=10_000)] = None,
    max_nodes: Annotated[int, Query(ge=10, le=MAX_NODES)] = 400,
) -> NeighbourhoodOut:
    """
    Users within k hops of the seeds, with the detector's hub caps (defaults:
    the run's engine config). Attributes over the cap are shown but not crossed.
    """
    seeds = [_parse_seed(s) for s in seed]
    ex = _explorer(source)
    cfg = _caps(source)
    for kind, ident in seeds:
        if not await _call(source, ex.r.exists, kind, ident):
            raise ApiError(404, "not_found", f"No {kind} {ident!r} in the {source} graph")
    params = {
        "seeds": [f"{k_}:{i}" for k_, i in seeds],
        "k": k,
        "rels": list(rel or RELS),
        "since_t": since_t,
        "until_t": until_t,
        "max_fanout": max_fanout or cfg.max_fanout,
        "far_fanout": far_fanout or cfg.far_fanout,
        "max_nodes": max_nodes,
        "hub_weight_method": ex.weight_method,
    }
    nb = await _call(
        source,
        ex.neighbourhood,
        seeds,
        k=k,
        max_fanout=params["max_fanout"],
        far_fanout=params["far_fanout"],
        rels=tuple(rel or RELS),
        window=Window(since_t, until_t),
        max_nodes=max_nodes,
    )
    return NeighbourhoodOut(source=source, **nb.to_dict(params))


def membership_timeline(members: set[str], history: list[dict[str, Any]]) -> list[RingMembership]:
    """Member set after each tracker change, rebuilt backwards from the current set."""
    after = set(members)
    states: list[RingMembership] = []
    for h in reversed(history):
        added, removed = list(h.get("added", [])), list(h.get("removed", []))
        details = {k: v for k, v in h.items() if k not in ("ts", "change", "added", "removed")}
        states.append(
            RingMembership(
                ts=h["ts"],
                change=h["change"],
                members=sorted(after),
                added=added,
                removed=removed,
                details=details,
            )
        )
        after = (after - set(added)) | set(removed)
    return list(reversed(states))


@graph.get(
    "/rings/{ring_id}", response_model=RingViewOut, operation_id="graph_ring", responses=ERRORS
)
async def ring_view(ring_id: str) -> RingViewOut:
    """A tracked ring of the current run: members and shared attributes over time."""
    if state.live is None:
        raise ApiError(409, "no_run", "No current run")
    ring = state.live.engine.tracker.rings.get(ring_id)
    if ring is None:
        raise ApiError(404, "not_found", f"No ring {ring_id!r} in the current run")
    ex = Explorer(MemoryReads(state.live.engine.store))
    # Shared attributes: links of all current members, kept when two or more share it.
    links = ex.r.links_of(set(ring.members))
    holders: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for lk in links:
        holders.setdefault((lk.kind, lk.attr), []).append({"user": lk.user, "t": lk.t})
    degree = ex.r.degree(set(holders))
    shared = [
        {
            "kind": kind,
            "id": attr,
            "degree": degree[(kind, attr)],
            "hub_weight": ex.weight(degree[(kind, attr)]),
            "members": sorted(hs, key=lambda h: (h["t"], h["user"])),
        }
        for (kind, attr), hs in sorted(holders.items())
        if len(hs) >= 2
    ]
    return RingViewOut(
        ring_id=ring.ring_id,
        run_id=state.run_id or "",
        status=ring.status.value,
        ring_type=ring.ring_type.value,
        risk=ring.risk,
        detectors=sorted(ring.sources),
        members=sorted(ring.members),
        first_seen=ring.first_seen.isoformat(),
        last_seen=ring.last_seen.isoformat(),
        parent=ring.parent,
        timeline=membership_timeline(ring.members, ring.history),
        size_history=list(ring.size_history),
        shared_attributes=shared,
    )
