"""
App-level audit: logins, logouts and admin actions go to the same hash-chained
trail as detection events (fraudsim.logging.audit.AuditTrail), in APP_AUDIT_DIR
(default runs/app_audit, run id "app"). Each entry is also referenced from the
app-state store (audit_refs) so app objects can link to their audit history.
`fraudsim audit-verify runs/app_audit` checks the chain.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from fraudsim.appdb.models import AuditRef
from fraudsim.logging.audit import AuditEntry, AuditTrail

APP_AUDIT_RUN_ID = "app"
_lock = threading.Lock()
_trails: dict[Path, AuditTrail] = {}


def audit_dir() -> Path:
    return Path(os.environ.get("APP_AUDIT_DIR", "runs/app_audit"))


def trail() -> AuditTrail:
    d = audit_dir()
    if d not in _trails:
        _trails[d] = AuditTrail(d, APP_AUDIT_RUN_ID)
    return _trails[d]


def record(
    action_type: str,
    actor: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any],
    db: Session | None = None,
) -> AuditEntry:
    """Append one entry (thread-safe) and, with a session, an audit_refs row."""
    with _lock:
        entry = trail().record(action_type, f"{object_type}:{object_id}", details, actor=actor)
    if db is not None:
        db.add(
            AuditRef(
                audit_run_id=APP_AUDIT_RUN_ID,
                entry_hash=entry.hash,
                action_type=action_type,
                object_type=object_type,
                object_id=object_id,
            )
        )
        db.commit()
    return entry
