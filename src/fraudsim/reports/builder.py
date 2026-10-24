"""
Investigation report builder.

collect()      scope -> report model (plain dict), from the app DB and run logs
render_html()  model -> HTML (Jinja2 template, print CSS, inline SVG charts)
render_pdf()   HTML -> PDF with headless Chromium (--print-to-pdf)

The model holds every number the report prints; the only value that changes
between two builds of the same scope is `generated_at`.

ASSUMPTION: PDF is printed by the headless Chromium that the web app's
Playwright already installs (no WeasyPrint native libraries on Windows, no new
Python dependency). `FRAUDSIM_CHROMIUM` overrides the executable.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from fraudsim import __version__
from fraudsim.appdb.models import Alert, Case, CaseAlert, Label, Note, User
from fraudsim.reports.charts import contributions_svg, evidence_svg
from fraudsim.reports.run_logs import ORACLE_LABEL, read_jsonl, run_dir, run_facts

EN_DASH = chr(0x2013)
DISCLAIMER = "Generated from simulated data for research/demo purposes. Not a regulatory filing."
SECTIONS = (
    "executive_summary",
    "alert_table",
    "ring_detail",
    "contributions",
    "counterfactuals",
    "timeline",
    "notes",
    "sar_summary",
    "run_metrics",
    "limitations",
)
TEMPLATES = Path(__file__).parent / "templates"


@dataclass
class ReportRequest:
    title: str
    run_ids: list[str] = field(default_factory=list)
    alert_ids: list[int] = field(default_factory=list)
    case_ids: list[int] = field(default_factory=list)
    since: datetime | None = None
    until: datetime | None = None
    sections: list[str] = field(default_factory=lambda: list(SECTIONS))
    oracle: bool = False
    format: str = "html"


class ReportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ─── Collecting ───────────────────────────────────────────────────────


def _name(db: Session | None, user_id: int | None) -> str | None:
    if db is None or user_id is None:
        return None
    u = db.get(User, user_id)
    return (u.display_name or u.email) if u else None


def _in_window(ts: str | datetime | None, req: ReportRequest) -> bool:
    if ts is None:
        return True
    t = datetime.fromisoformat(ts) if isinstance(ts, str) else ts
    if t.tzinfo is None and req.since is not None and req.since.tzinfo is not None:
        t = t.replace(tzinfo=req.since.tzinfo)
    return (req.since is None or t >= req.since) and (req.until is None or t <= req.until)


def _notes(db: Session | None, **where: Any) -> list[dict[str, Any]]:
    """Current version of each note, oldest first (edited notes say so)."""
    if db is None:
        return []
    rows = db.scalars(select(Note).filter_by(**where).order_by(Note.id)).all()
    superseded = {n.supersedes_id for n in rows if n.supersedes_id is not None}
    return [
        {
            "author": _name(db, n.author_id),
            "created_at": n.created_at.isoformat(),
            "body": n.body,
            "edited": n.supersedes_id is not None,
        }
        for n in rows
        if n.id not in superseded
    ]


def _sentences(text: str | None) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=\.)\s+", text or "") if s.strip()]


def _ring_entry(
    db: Session | None,
    run_id: str,
    ref: str,
    alert: Alert | None,
    logged: dict[str, Any] | None,
    snapshot: tuple[dict[str, Any], str | None] | None,
    case_ids: list[int],
) -> dict[str, Any]:
    """One ring of the report: the frozen case snapshot if any, else the app-DB
    alert, else the run log's first alert/early-warning record."""
    exp: dict[str, Any] = {}
    if alert is not None:
        exp = dict(alert.explanation or {})
    elif logged is not None:
        exp = dict(logged.get("explanation") or {})
    snap, snap_hash = snapshot if snapshot else ({}, None)
    evidence = snap.get("evidence_subgraph") or exp.get("evidence_subgraph") or {}
    risk = snap.get("risk", alert.risk if alert else (logged or {}).get("risk"))
    labels: list[dict[str, Any]] = []
    if db is not None:
        labels = [
            {
                "label": lb.label.value,
                "author": _name(db, lb.author_id),
                "at": lb.created_at.isoformat(),
            }
            for lb in db.scalars(
                select(Label)
                .where(Label.run_id == run_id, Label.alert_ref == ref)
                .order_by(Label.id)
            )
        ]
    members = sorted(
        snap.get("members") or (alert.members if alert else (logged or {}).get("members", []))
    )
    transfers = [e for e in evidence.get("edges", []) if e.get("type") == "transfer"]
    return {
        "run_id": run_id,
        "ring_id": ref,
        "alert_id": alert.id if alert else None,
        "kind": alert.kind if alert else (logged or {}).get("change"),
        "status": alert.status.value if alert else None,
        "assignee": _name(db, alert.assignee_id) if alert else None,
        "ring_type": snap.get("ring_type")
        or (alert.ring_type if alert else (logged or {}).get("ring_type"))
        or "unknown",
        "risk": risk,
        "threshold": snap.get("threshold", alert.threshold if alert else exp.get("threshold")),
        "calibration_bucket": (
            alert.calibration_bucket if alert else exp.get("calibration_bucket")
        ),
        "detectors": sorted(
            snap.get("detectors")
            or (alert.detectors if alert else (logged or {}).get("detectors", []))
        ),
        "members": members,
        "reason": snap.get("reason") or exp.get("reason_text") or (alert.reason if alert else None),
        "first_seen": alert.first_seen_at.isoformat() if alert else (logged or {}).get("ts"),
        "last_seen": alert.last_seen_at.isoformat() if alert else (logged or {}).get("ts"),
        "history": list(alert.history) if alert else [],
        "contributions": exp.get("feature_contributions") or {},
        "counterfactuals": _sentences(exp.get("counterfactual")),
        "evidence": evidence,
        "shared_attributes": sorted(
            (
                {
                    "kind": n["type"],
                    "id": n["id"],
                    "degree": n.get("degree"),
                    "hub_weight": n.get("hub_weight"),
                }
                for n in evidence.get("nodes", [])
                if n.get("type") != "user"
            ),
            key=lambda a: (a["kind"], a["id"]),
        ),
        "transfers": {
            "count": len(transfers),
            "amount": round(sum(float(t.get("amount", 0)) for t in transfers), 2),
        },
        "snapshot_sha256": snap_hash,
        "case_ids": case_ids,
        "labels": labels,
        "notes": _notes(db, run_id=run_id, alert_ref=ref),
    }


def collect(
    db: Session | None, req: ReportRequest, runs_root: Path | None = None
) -> dict[str, Any]:
    """The report model for a scope. `db` may be None for a logs-only report."""
    unknown = set(req.sections) - set(SECTIONS)
    if unknown:
        raise ReportError("validation_error", f"Unknown sections: {', '.join(sorted(unknown))}")
    rings: dict[tuple[str, str], dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    snapshots: dict[tuple[str, str], tuple[dict[str, Any], str | None]] = {}
    ring_cases: dict[tuple[str, str], list[int]] = {}
    alerts: dict[tuple[str, str], Alert] = {}

    if db is not None:
        for cid in sorted(set(req.case_ids)):
            c = db.get(Case, cid)
            if c is None:
                raise ReportError("not_found", f"No case {cid}")
            links = db.scalars(
                select(CaseAlert).where(CaseAlert.case_id == cid).order_by(CaseAlert.id)
            ).all()
            for ca in links:
                key = (ca.run_id, ca.alert_ref)
                snapshots.setdefault(key, (ca.evidence_snapshot or {}, ca.snapshot_sha256))
                ring_cases.setdefault(key, []).append(cid)
            cases.append(
                {
                    "id": c.id,
                    "title": c.title,
                    "status": c.status.value,
                    "priority": c.priority.value,
                    "resolution": c.resolution,
                    "assignee": _name(db, c.assignee_id),
                    "created_by": _name(db, c.created_by_id),
                    "created_at": c.created_at.isoformat(),
                    "alert_refs": [f"{ca.alert_ref}" for ca in links],
                    "notes": _notes(db, case_id=c.id),
                }
            )
        for aid in sorted(set(req.alert_ids)):
            a = db.get(Alert, aid)
            if a is None:
                raise ReportError("not_found", f"No alert {aid}")
            alerts[(a.run_id, a.alert_ref)] = a
        for key in snapshots:
            if key not in alerts:
                a = db.scalar(
                    select(Alert).where(Alert.run_id == key[0], Alert.alert_ref == key[1])
                )
                if a is not None:
                    alerts[key] = a

    run_ids = sorted(set(req.run_ids) | {k[0] for k in alerts} | {k[0] for k in snapshots})
    runs: list[dict[str, Any]] = []
    for rid in run_ids:
        d = run_dir(rid, runs_root)
        facts = run_facts(d, oracle=req.oracle) if d is not None else None
        runs.append({"run_id": rid, "logs": d is not None, "facts": facts})
        # A run in scope with no explicit alerts: every ring it raised (app DB row
        # when recorded, else the run log's first alert/early-warning record).
        if rid in req.run_ids and not req.alert_ids and not req.case_ids:
            logged_first: dict[str, dict[str, Any]] = {}
            ring_types: dict[str, str] = {}
            if d is not None:
                ring_types = {r["ring_id"]: r["ring_type"] for r in read_jsonl(d / "rings.jsonl")}
                for rec in read_jsonl(d / "detections.jsonl"):
                    if rec["change"] in ("alert", "early_warning"):
                        rec = {**rec, "ring_type": ring_types.get(rec["ring_id"])}
                        logged_first.setdefault(rec["ring_id"], rec)
            refs = set(logged_first)
            if db is not None:
                for a in db.scalars(select(Alert).where(Alert.run_id == rid)):
                    alerts.setdefault((rid, a.alert_ref), a)
                    refs.add(a.alert_ref)
            for ref in sorted(refs):
                key = (rid, ref)
                rings[key] = _ring_entry(
                    db, rid, ref, alerts.get(key), logged_first.get(ref), None, []
                )
    for key, a in alerts.items():
        if key not in rings:
            rings[key] = _ring_entry(
                db, key[0], key[1], a, None, snapshots.get(key), ring_cases.get(key, [])
            )
    for key, snap in snapshots.items():
        if key not in rings:
            rings[key] = _ring_entry(db, key[0], key[1], None, None, snap, ring_cases.get(key, []))

    selected = [r for _, r in sorted(rings.items()) if _in_window(r["first_seen"], req)]
    selected.sort(
        key=lambda r: (-(r["risk"] if r["risk"] is not None else -1), r["run_id"], r["ring_id"])
    )
    for r in selected:
        r["contributions_svg"] = (
            contributions_svg(r["contributions"]) if "contributions" in req.sections else None
        )
        r["evidence_svg"] = evidence_svg(r["evidence"]) if "ring_detail" in req.sections else None
    return {
        "title": req.title,
        "version": __version__,
        "scope": {
            "run_ids": req.run_ids,
            "alert_ids": req.alert_ids,
            "case_ids": req.case_ids,
            "since": req.since.isoformat() if req.since else None,
            "until": req.until.isoformat() if req.until else None,
            "oracle": req.oracle,
        },
        "sections": [s for s in SECTIONS if s in req.sections],
        "cases": cases,
        "rings": selected,
        "runs": runs,
        "run_ids": run_ids,
        "config_hashes": sorted(
            {r["facts"]["config_hash"] for r in runs if r["facts"] and r["facts"]["config_hash"]}
        ),
        "summary": _summary(selected, cases, runs),
        "sar": _sar(selected, cases, runs),
        "oracle_label": ORACLE_LABEL,
        "disclaimer": DISCLAIMER,
    }


def _summary(
    rings: list[dict[str, Any]], cases: list[dict[str, Any]], runs: list[dict[str, Any]]
) -> dict[str, Any]:
    types: dict[str, int] = {}
    for r in rings:
        types[r["ring_type"]] = types.get(r["ring_type"], 0) + 1
    risks = [r["risk"] for r in rings if r["risk"] is not None]
    return {
        "rings": len(rings),
        "alerts": sum(1 for r in rings if r["kind"] == "alert"),
        "early_warnings": sum(1 for r in rings if r["kind"] == "early_warning"),
        "cases": len(cases),
        "runs": len(runs),
        "ring_types": dict(sorted(types.items())),
        "max_risk": max(risks) if risks else None,
        "members": len({m for r in rings for m in r["members"]}),
        "labelled": sum(1 for r in rings if r["labels"]),
    }


def _sar(
    rings: list[dict[str, Any]], cases: list[dict[str, Any]], runs: list[dict[str, Any]]
) -> dict[str, Any]:
    """SAR-style summary (structure only: this is not a suspicious-activity report)."""
    times = sorted(t for r in rings for t in (r["first_seen"], r["last_seen"]) if t)
    return {
        "subjects": sorted({m for r in rings for m in r["members"]}),
        "attributes": sorted(
            {f"{a['kind']}:{a['id']}" for r in rings for a in r["shared_attributes"]}
        ),
        "transfers": sum(r["transfers"]["count"] for r in rings),
        "amount": round(sum(r["transfers"]["amount"] for r in rings), 2),
        "first": times[0] if times else None,
        "last": times[-1] if times else None,
        "typology": sorted({r["ring_type"] for r in rings}),
        "detectors": sorted({d for r in rings for d in r["detectors"]}),
        "evidence": [
            {
                "run_id": r["run_id"],
                "ring_id": r["ring_id"],
                "snapshot_sha256": r["snapshot_sha256"],
            }
            for r in rings
        ],
        "narrative": [n for c in cases for n in c["notes"]]
        + [n for r in rings for n in r["notes"]],
    }


# ─── Rendering ────────────────────────────────────────────────────────


def _fmt(v: Any, digits: int = 2) -> str:
    if v is None:
        return EN_DASH
    if isinstance(v, float):
        return f"{v:,.{digits}f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)
_env.filters["fmt"] = _fmt
_env.filters["words"] = lambda s: str(s or "").replace("_", " ")


def render_html(model: dict[str, Any], generated_at: str) -> str:
    return _env.get_template("report.html.j2").render(m=model, generated_at=generated_at)


def chromium_path() -> str | None:
    """FRAUDSIM_CHROMIUM, else a Playwright-installed headless shell or Chromium."""
    explicit = os.environ.get("FRAUDSIM_CHROMIUM")
    if explicit:
        return explicit if Path(explicit).exists() else None
    roots: list[Path] = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        roots.append(Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright")
    roots += [
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / "Library/Caches/ms-playwright",
    ]
    patterns = (
        "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell*",
        "chromium-*/chrome-*/chrome",
        "chromium-*/chrome-*/chrome.exe",
    )
    for root in roots:
        for pattern in patterns:
            hits = sorted(p for p in root.glob(pattern) if p.is_file() and p.suffix in ("", ".exe"))
            if hits:
                return str(hits[-1])
    for name in ("chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def render_pdf(html: str) -> bytes:
    exe = chromium_path()
    if exe is None:
        raise ReportError(
            "pdf_unavailable",
            "PDF needs headless Chromium (cd webapp && npx playwright install chromium, "
            "or set FRAUDSIM_CHROMIUM); HTML reports work without it",
        )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "report.html"
        out = Path(tmp) / "report.pdf"
        src.write_text(html, encoding="utf-8")
        proc = subprocess.run(  # fixed arguments, local executable
            [
                exe,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--no-pdf-header-footer",
                f"--print-to-pdf={out}",
                src.resolve().as_uri(),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
        if not out.exists() or out.stat().st_size == 0:
            raise ReportError(
                "pdf_failed",
                f"Chromium did not write a PDF: {proc.stderr.decode(errors='replace')[-300:]}",
            )
        return out.read_bytes()
