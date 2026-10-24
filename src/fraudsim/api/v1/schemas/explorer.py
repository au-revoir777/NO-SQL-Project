"""Entity and graph explorer (P6)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Source = Literal["run", "course", "neo4j"]
Kind = Literal["user", "device", "card", "ip"]
Rel = Literal["device", "card", "ip", "transfer"]


class EntityHit(BaseModel):
    kind: Kind
    id: str
    degree: int = Field(description="Users: attributes linked; attributes: active users")


class EntityAlert(BaseModel):
    id: int
    alert_ref: str
    status: str
    risk: float | None
    ring_type: str


class EntityRing(BaseModel):
    ring_id: str
    status: str
    ring_type: str
    members: int
    risk: float | None


class EntityLink(BaseModel):
    kind: Kind
    id: str
    t: float = Field(description="Last time the link was made (simulated epoch seconds)")
    degree: int
    hub_weight: float


class EntityUser(BaseModel):
    id: str
    t: float


class TxnItem(BaseModel):
    txn_id: str
    t: float
    direction: Literal["in", "out"]
    counterparty: str
    amount: float


class TxnSummary(BaseModel):
    sent: int
    received: int
    amount_sent: float
    amount_received: float
    items: list[TxnItem] = Field(description="The latest transfers, oldest first")
    truncated: bool


class TimelineItem(BaseModel):
    t: float
    type: Literal["joined", "linked", "sent", "received"]
    kind: str | None = None
    id: str | None = None
    amount: float | None = None
    counterparty: str | None = None
    txn_id: str | None = None


class EntityDetail(BaseModel):
    source: Source
    kind: Kind
    id: str
    degree: int
    active: bool | None = None
    joined_t: float | None = None
    hub_weight: float | None = Field(
        None, description="Attributes: weight the hub-aware detector gives"
    )
    hub_weight_method: str | None = None
    is_hub: bool | None = Field(None, description="Degree above the engine's far_fanout cap")
    attributes: list[EntityLink] = Field(
        default_factory=list, description="Users: linked attributes with degree and hub weight"
    )
    users: list[EntityUser] = Field(
        default_factory=list, description="Attributes: active users linked, with link time"
    )
    transactions: TxnSummary | None = Field(
        None, description="Users: counts, totals and the latest transfers in and out"
    )
    timeline: list[TimelineItem]
    alerts: list[EntityAlert] = Field(default_factory=list)
    rings: list[EntityRing] = Field(default_factory=list)


class StopOut(BaseModel):
    hop: int
    degree: int
    cap: int | None = Field(description="The cap that stopped the walk; null for the depth limit")
    reason: str


class GraphNodeOut(BaseModel):
    key: str
    kind: Kind
    id: str
    hop: int
    seed: bool
    active: bool | None = None
    joined_t: float | None = None
    degree: int | None = None
    hub_weight: float | None = None
    hub: bool | None = None
    stop: StopOut | None = Field(
        None, description="Why the walk did not cross this attribute (hub cap or depth limit)"
    )


class GraphEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    kind: Rel
    t: float
    weight: float | None = Field(None, description="Hub weight of the shared attribute")
    amount: float | None = None
    txn_id: str | None = None


class NeighbourhoodOut(BaseModel):
    source: Source
    params: dict[str, Any]
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    truncated: bool = Field(description="The walk stopped at max_nodes")


class RingMembership(BaseModel):
    ts: str
    change: str
    members: list[str]
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class SharedHolder(BaseModel):
    user: str
    t: float


class SharedAttribute(BaseModel):
    kind: Kind
    id: str
    degree: int
    hub_weight: float
    members: list[SharedHolder]


class RingViewOut(BaseModel):
    ring_id: str
    run_id: str
    status: str
    ring_type: str
    risk: float | None
    detectors: list[str]
    members: list[str]
    first_seen: str
    last_seen: str
    parent: str | None
    timeline: list[RingMembership] = Field(
        description="Member set after each change (created, grew, shrank, merged, split, ...)"
    )
    size_history: list[tuple[float, int]]
    shared_attributes: list[SharedAttribute] = Field(
        description="Attributes shared by at least two current members"
    )
