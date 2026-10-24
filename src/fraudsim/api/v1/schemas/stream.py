"""Live-dashboard payloads (P3): KPI samples and alerts, as sent over SSE."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetectLatency(BaseModel):
    count: int
    p50: float | None
    p95: float | None
    p99: float | None


class RingsByStatus(BaseModel):
    candidate: int
    confirmed: int
    dissolved: int


class OracleMetrics(BaseModel):
    """Simulator ground truth; only shown behind the Oracle toggle."""

    label: str = "Oracle (simulator ground truth)"
    ring_precision: float | None
    ring_recall: float | None
    ring_f1: float | None
    true_rings: int | None
    rings_detected: int | None
    missed_rings: int | None


class RunMetricsV1(BaseModel):
    """KPIs of the live run, read from the running engine (no stored or sample data)."""

    run_id: str
    status: str
    scenario: str
    seed: int
    sim_time_s: float
    events_total: int
    events_per_s: float = Field(description="Achieved event rate, events per wall-clock second")
    batches: int
    graph: dict[str, int]
    rings_by_status: RingsByStatus
    alerts_total: int
    open_alerts: int
    alerts_per_sim_hour: float | None = Field(
        description="Alerts per simulated hour; scenarios run compressed, not an operational rate"
    )
    detect_ms: DetectLatency
    oracle: OracleMetrics | None = None


class AlertV1(BaseModel):
    """One alert or early warning as published to `fraudsim:alerts`."""

    run_id: str
    ring_id: str
    kind: str = Field(description="alert | early_warning")
    ts: str
    sim_time_s: float
    risk: float | None
    threshold: float | None
    ring_type: str | None
    status: str | None
    members_count: int
    members: list[str]
    detectors: list[str]
    top_reason: str | None
