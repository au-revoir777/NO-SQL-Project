"""
Status machines for alert triage and cases (P5).

Alerts: new -> triaged | escalated | closed; triaged -> escalated | closed;
escalated -> triaged | closed. Cases: open -> in_review | escalated | closed;
in_review -> open | escalated | closed; escalated -> in_review | closed.
Closed is final for analysts; an admin may reopen (alert -> triaged, case ->
in_review). Closing a case needs a resolution. Setting the current status
again is a no-op, not an error.
"""

from __future__ import annotations

from fraudsim.api.v1.errors import ApiError
from fraudsim.appdb.models import AlertStatus, CaseStatus

ALERT_TRANSITIONS: dict[AlertStatus, set[AlertStatus]] = {
    AlertStatus.NEW: {AlertStatus.TRIAGED, AlertStatus.ESCALATED, AlertStatus.CLOSED},
    AlertStatus.TRIAGED: {AlertStatus.ESCALATED, AlertStatus.CLOSED},
    AlertStatus.ESCALATED: {AlertStatus.TRIAGED, AlertStatus.CLOSED},
    AlertStatus.CLOSED: set(),
}
ALERT_REOPEN = AlertStatus.TRIAGED

CASE_TRANSITIONS: dict[CaseStatus, set[CaseStatus]] = {
    CaseStatus.OPEN: {CaseStatus.IN_REVIEW, CaseStatus.ESCALATED, CaseStatus.CLOSED},
    CaseStatus.IN_REVIEW: {CaseStatus.OPEN, CaseStatus.ESCALATED, CaseStatus.CLOSED},
    CaseStatus.ESCALATED: {CaseStatus.IN_REVIEW, CaseStatus.CLOSED},
    CaseStatus.CLOSED: set(),
}
CASE_REOPEN = CaseStatus.IN_REVIEW


def check_alert(old: AlertStatus, new: AlertStatus, is_admin: bool) -> None:
    if new == old or new in ALERT_TRANSITIONS[old]:
        return
    if old == AlertStatus.CLOSED and new == ALERT_REOPEN and is_admin:
        return
    raise ApiError(
        409,
        "invalid_transition",
        f"An alert cannot go from {old.value} to {new.value}"
        + (" (only an admin can reopen a closed alert)" if old == AlertStatus.CLOSED else ""),
        details=[
            {
                "from": old.value,
                "to": new.value,
                "allowed": sorted(s.value for s in ALERT_TRANSITIONS[old]),
            }
        ],
    )


def check_case(old: CaseStatus, new: CaseStatus, is_admin: bool, resolution: str | None) -> None:
    if new == CaseStatus.CLOSED and old != CaseStatus.CLOSED and not (resolution or "").strip():
        raise ApiError(422, "validation_error", "Closing a case needs a resolution")
    if new == old or new in CASE_TRANSITIONS[old]:
        return
    if old == CaseStatus.CLOSED and new == CASE_REOPEN and is_admin:
        return
    raise ApiError(
        409,
        "invalid_transition",
        f"A case cannot go from {old.value} to {new.value}"
        + (" (only an admin can reopen a closed case)" if old == CaseStatus.CLOSED else ""),
        details=[
            {
                "from": old.value,
                "to": new.value,
                "allowed": sorted(s.value for s in CASE_TRANSITIONS[old]),
            }
        ],
    )
