"""
Persist alerts as the live run raises them (P5).

`AlertRecorder.on_update` is called by the stream publisher for every ring
update. The first `alert` or `early_warning` of a tracked ring creates an
`alerts` row with the ring's explanation and evidence; later updates of that
ring refresh its members, risk, explanation and `history`. Triage fields
(status, assignee) are never touched here. A database problem is logged and
never interrupts the live run.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select

from fraudsim import appdb
from fraudsim.appdb.models import Alert

logger = structlog.get_logger(__name__)

RAISING = ("alert", "early_warning")
MAX_HISTORY = 200


def _snapshot(ring: Any) -> dict[str, Any]:
    exp = dict(ring.explanation or {})
    return {
        "ring_type": ring.ring_type.value,
        "ring_status": ring.status.value,
        "risk": ring.risk,
        "threshold": exp.get("threshold"),
        "calibration_bucket": exp.get("calibration_bucket") or None,
        "members": sorted(ring.members),
        "detectors": sorted(ring.sources),
        "reason": exp.get("reason_text"),
        "explanation": exp or None,
    }


class AlertRecorder:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.known: set[str] = set()  # alert_refs already stored for this run
        self.failed = False

    def on_update(self, live: Any, update: dict[str, Any]) -> None:
        ref = update["ring_id"]
        change = update.get("change")
        if ref not in self.known and change not in RAISING:
            return
        ring = live.engine.tracker.rings.get(ref)
        if ring is None:
            return
        ts = datetime.fromisoformat(update["ts"])
        entry = {
            "ts": update["ts"],
            "change": change,
            "status": update.get("status"),
            "members": len(update.get("members") or []),
            "score": update.get("score"),
            "details": update.get("details") or {},
        }
        try:
            db = appdb.open_session()
            try:
                row = db.scalar(
                    select(Alert).where(Alert.run_id == self.run_id, Alert.alert_ref == ref)
                )
                snap = _snapshot(ring)
                if row is None:
                    sim_s = float(live.snapshot().get("sim_time_s", 0.0))
                    row = Alert(
                        run_id=self.run_id,
                        alert_ref=ref,
                        kind=change,
                        first_seen_at=ts,
                        last_seen_at=ts,
                        sim_time_s=round(sim_s, 3),
                        history=[entry],
                        **snap,
                    )
                    db.add(row)
                else:
                    for k, v in snap.items():
                        setattr(row, k, v)
                    row.last_seen_at = ts
                    row.history = [*row.history, entry][-MAX_HISTORY:]
                db.commit()
            finally:
                db.close()
            self.known.add(ref)
        except Exception as exc:  # the live run must not stop because of the app DB
            if not self.failed:
                logger.warning("alert_recording_failed", error=str(exc), run_id=self.run_id)
            self.failed = True
