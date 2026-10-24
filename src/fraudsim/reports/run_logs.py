"""
Facts about one run, read only from its log directory (manifest.json,
events.jsonl, detections.jsonl and, for the Oracle section, ground_truth.jsonl).

Every number a report shows about a run comes from here, so it can be checked
against the logs (tests/test_reports.py recomputes them independently).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from fraudsim.metrics.matching import jaccard

ORACLE_LABEL = "Oracle (simulator ground truth)"
MATCH_JACCARD = 0.5


def runs_root() -> Path:
    return Path(os.environ.get("FRAUDSIM_RUNS_DIR", "runs"))


def run_dir(run_id: str, root: Path | None = None) -> Path | None:
    """Log directory of a run: runs/live/<id> (API runs) or runs/<id> (CLI runs)."""
    base = root or runs_root()
    for d in (base / "live" / run_id, base / run_id):
        if (d / "manifest.json").exists():
            return d
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_facts(directory: Path, oracle: bool = False) -> dict[str, Any]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    events = read_jsonl(directory / "events.jsonl")
    detections = read_jsonl(directory / "detections.jsonl")
    by_type = Counter(e["event_type"] for e in events)
    txns = [e for e in events if e["event_type"] == "transaction"]
    ts = sorted(e["ts"] for e in events)
    changes = Counter(d["change"] for d in detections)
    raised = [d for d in detections if d["change"] in ("alert", "early_warning")]
    model = manifest.get("model") or {}
    facts: dict[str, Any] = {
        "run_id": manifest["run_id"],
        "scenario": manifest.get("scenario"),
        "seed": manifest.get("seed"),
        "config_hash": manifest.get("scenario_hash"),
        "stream_digest": manifest.get("stream_digest"),
        "model_sha256": model.get("sha256"),
        "model_path": Path(str(model["path"])).name if model.get("path") else None,
        "engine": manifest.get("engine", {}),
        "events": len(events),
        "events_by_type": dict(sorted(by_type.items())),
        "transactions": len(txns),
        "transaction_amount": round(sum(float(e["payload"]["amount"]) for e in txns), 2),
        "first_event_ts": ts[0] if ts else None,
        "last_event_ts": ts[-1] if ts else None,
        "ring_updates": len(detections),
        "ring_updates_by_change": dict(sorted(changes.items())),
        "rings_tracked": len({d["ring_id"] for d in detections}),
        "alerts_raised": changes.get("alert", 0),
        "early_warnings_raised": changes.get("early_warning", 0),
        "raised": [
            {
                "ring_id": d["ring_id"],
                "change": d["change"],
                "ts": d["ts"],
                "risk": d.get("risk"),
                "members": sorted(d.get("members", [])),
                "detectors": d.get("detectors", []),
            }
            for d in raised
        ],
    }
    if oracle:
        facts["oracle"] = oracle_comparison(directory, raised)
    return facts


def oracle_comparison(directory: Path, raised: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Raised rings (members when raised) matched one-to-one to simulator rings
    (every member that ever joined) at Jaccard >= 0.5, best pairs first.
    """
    truth = read_jsonl(directory / "ground_truth.jsonl")
    if not truth:
        return {"label": ORACLE_LABEL, "available": False}
    true_sets = {
        r["ring_id"]: {h["user_id"] for h in r.get("member_history", []) if h["action"] == "join"}
        | set(r.get("members", []))
        for r in truth
    }
    flagged: dict[str, set[str]] = {}
    for d in raised:  # first raise of each ring
        flagged.setdefault(d["ring_id"], set(d.get("members", [])))
    pairs = sorted(
        (
            (jaccard(m, t), fid, tid)
            for fid, m in flagged.items()
            for tid, t in true_sets.items()
            if jaccard(m, t) >= MATCH_JACCARD
        ),
        key=lambda p: (-p[0], p[1], p[2]),
    )
    used_f: set[str] = set()
    used_t: set[str] = set()
    matches = []
    for j, fid, tid in pairs:
        if fid in used_f or tid in used_t:
            continue
        used_f.add(fid)
        used_t.add(tid)
        matches.append({"ring_id": fid, "true_ring_id": tid, "jaccard": round(j, 4)})
    tp = len(matches)
    return {
        "label": ORACLE_LABEL,
        "available": True,
        "true_rings": len(true_sets),
        "raised_rings": len(flagged),
        "matched": tp,
        "precision": round(tp / len(flagged), 4) if flagged else None,
        "recall": round(tp / len(true_sets), 4) if true_sets else None,
        "matches": matches,
        "missed": sorted(set(true_sets) - used_t),
        "unmatched_raised": sorted(set(flagged) - used_f),
        "match_rule": f"Jaccard >= {MATCH_JACCARD} on members, one-to-one, best first",
    }
