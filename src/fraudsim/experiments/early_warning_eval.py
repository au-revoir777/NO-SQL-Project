"""
E11: early-warning lead time without look-ahead (docs/research/e11_protocol.md).

A warning qualifies for a true ring only through the members shown at the
warning (RingUpdate.members) and the true ring's members who had joined by that
moment, so nothing after the warning is used. The old final-member count
(scoring.early_warning.lead_times) is computed on the same runs for comparison.

    fraudsim experiment --suite early_warning --seeds 10
    python -m fraudsim.experiments.early_warning_eval --results-dir results/
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fraudsim.experiments.alert_units import SCENARIOS, run_scored
from fraudsim.experiments.harness import _append, make_stream
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.logging.replay import file_sha256
from fraudsim.scoring.early_warning import lead_times
from fraudsim.scoring.scorer import RingScorer
from fraudsim.types import GroundTruthRing

MIN_OVERLAP = 2
MIN_PRECISION = 0.66
BOOTSTRAP = 2000
MIN_TYPE_RINGS = 10


def joined_by(ring: GroundTruthRing, t: datetime) -> set[str]:
    """Every account that joined `ring` at or before t (leavers included)."""
    return {u for ts, action, u in ring.member_history if action == "join" and ts <= t}


def qualifies(members: frozenset[str] | set[str], known: set[str]) -> bool:
    inter = len(set(members) & known)
    return inter >= MIN_OVERLAP and inter / max(len(members), 1) >= MIN_PRECISION


def warnings_of(reports: list[Any]) -> list[Any]:
    """All early_warning and alert updates, in time order."""
    ups = [u for rep in reports for u in rep.updates if u.change in ("early_warning", "alert")]
    return sorted(ups, key=lambda u: (u.ts, u.ring_id, u.change))


def evaluate(
    ledger: Any, reports: list[Any], start: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Per true ring lead times and per tracked-ring first-early-warning precision."""
    ups = warnings_of(reports)
    rings_out = []
    for g in sorted(ledger.rings.values(), key=lambda r: r.ring_id):
        eligible = (
            g.activate_ts is not None and g.spawn_ts is not None and g.activate_ts > g.spawn_ts
        )
        first_any = first_ew = None
        for u in ups:
            need_any = first_any is None
            need_ew = first_ew is None and u.change == "early_warning"
            if (need_any or need_ew) and qualifies(frozenset(u.members), joined_by(g, u.ts)):
                if need_any:
                    first_any = u
                if need_ew:
                    first_ew = u
            if first_any is not None and first_ew is not None:
                break

        rings_out.append(
            {
                "true_ring": g.ring_id,
                "type": g.ring_type.value,
                "evasion": g.evasion_mode.value,
                "eligible": eligible,
                "spawn_s": _rel(g.spawn_ts, start),
                "activate_s": _rel(g.activate_ts, start),
                "forming_s": round((g.activate_ts - g.spawn_ts).total_seconds(), 3)
                if eligible
                else None,
                "first_warning_s": _rel(first_any.ts, start) if first_any else None,
                "first_warning_kind": first_any.change if first_any else None,
                "lead_s": _lead(g, first_any),
                "first_early_warning_s": _rel(first_ew.ts, start) if first_ew else None,
                "lead_early_warning_s": _lead(g, first_ew),
            }
        )
    seen: set[str] = set()
    warn_out = []
    for u in ups:
        if u.change != "early_warning" or u.ring_id in seen:
            continue
        seen.add(u.ring_id)
        spawned = [
            g for g in ledger.rings.values() if g.spawn_ts is not None and g.spawn_ts <= u.ts
        ]
        shown = frozenset(u.members)
        hit = sorted(g.ring_id for g in spawned if qualifies(shown, joined_by(g, u.ts)))
        warn_out.append(
            {
                "ring_id": u.ring_id,
                "t_s": _rel(u.ts, start),
                "size": len(u.members),
                "correct": bool(hit),
                "matches": ";".join(hit),
            }
        )
    return rings_out, warn_out


def _lead(g: GroundTruthRing, u: Any) -> float | None:
    """Activation minus warning time (positive: warned while the ring was forming)."""
    if u is None or g.activate_ts is None:
        return None
    return round((g.activate_ts - u.ts).total_seconds(), 3)


def _rel(ts: datetime | None, start: datetime) -> float | None:
    return round((ts - start).total_seconds(), 3) if ts is not None else None


def run_e11(
    out: Path,
    test_seeds: list[int],
    log: Callable[[str], None] = print,
    scenarios: tuple[str, ...] = SCENARIOS,
    model_path: Path | None = None,
    scenario_overrides: dict[str, Any] | None = None,
) -> Path:
    from fraudsim.experiments.harness import DEFAULT_MODEL
    from fraudsim.experiments.suite import tuned_proposed

    model_path = Path(model_path or DEFAULT_MODEL)
    scorer = RingScorer.load(model_path)
    method = tuned_proposed()
    out_dir = Path(out) / "e11_early_warning"
    details = {
        "protocol": "docs/research/e11_protocol.md",
        "method": method.config() | {"label": method.label},
        "scenarios": list(scenarios),
        "seeds": list(test_seeds),
        "thresholds": {"min_overlap": MIN_OVERLAP, "min_precision": MIN_PRECISION},
        "scenario_overrides": scenario_overrides or {},
        "model": {"path": repo_relative(model_path), "sha256": file_sha256(model_path)},
    }
    with recorded(out_dir, "e11_early_warning", details):
        for scenario in scenarios:
            for seed in test_seeds:
                stream = make_stream(scenario, seed, scenario_overrides)
                engine, _ = run_scored(stream, method, scorer, record=False)
                gen = stream.generator
                start = gen.ts(0.0)
                rings, warns = evaluate(gen.ledger, engine.reports, start)
                old = lead_times(gen.ledger, engine.tracker)
                base = {"scenario": scenario, "seed": seed, "stream_digest": gen.digest[:16]}
                for r in rings:
                    _append(out_dir / "rings.csv", base | r)
                for w in warns:
                    _append(out_dir / "warnings.csv", base | w)
                eligible = [r for r in rings if r["eligible"]]
                run = base | {
                    "sim_hours": round((gen.ts() - start).total_seconds() / 3600.0, 6),
                    "true_rings": len(rings),
                    "eligible_rings": len(eligible),
                    "warned_before_activation": sum(
                        1 for r in eligible if r["lead_s"] is not None and r["lead_s"] > 0
                    ),
                    "early_warned_before_activation": sum(
                        1
                        for r in eligible
                        if r["lead_early_warning_s"] is not None and r["lead_early_warning_s"] > 0
                    ),
                    "first_early_warnings": len(warns),
                    "false_early_warnings": sum(1 for w in warns if not w["correct"]),
                    "old_metric_before_activation": sum(
                        1 for x in old if x["lead_time_s"] is not None and x["lead_time_s"] > 0
                    ),
                }
                _append(out_dir / "results.csv", run)
                log(
                    f"[e11] {scenario} seed={seed} eligible={run['eligible_rings']} "
                    f"warned={run['warned_before_activation']} "
                    f"(old {run['old_metric_before_activation']}) "
                    f"false_ew={run['false_early_warnings']}/{run['first_early_warnings']}"
                )
    return out_dir


# ─── Analysis ─────────────────────────────────────────────────────────────────


def _share(df: pd.DataFrame, col: str) -> float | None:
    return float(df[col].mean()) if len(df) else None


def _boot(
    df: pd.DataFrame, stat: Callable[[pd.DataFrame], float | None], rng: np.random.Generator
) -> tuple[float, float] | None:
    by = {s: [g for _, g in sc.groupby("seed")] for s, sc in df.groupby("scenario")}
    vals = []
    for _ in range(BOOTSTRAP):
        parts = []
        for runs in by.values():
            parts += [runs[i] for i in rng.integers(0, len(runs), len(runs))]
        v = stat(pd.concat(parts, ignore_index=True)) if parts else None
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            vals.append(v)
    if len(vals) < BOOTSTRAP // 2:
        return None
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def analyse(results_dir: Path, seed: int = 0) -> dict[str, pd.DataFrame]:
    d = Path(results_dir) / "e11_early_warning"
    rings = pd.read_csv(d / "rings.csv")
    warns = pd.read_csv(d / "warnings.csv") if (d / "warnings.csv").exists() else pd.DataFrame()
    runs = pd.read_csv(d / "results.csv")
    rings["warned"] = rings["lead_s"].fillna(-1) > 0
    rings["early_warned"] = rings["lead_early_warning_s"].fillna(-1) > 0
    el = rings[rings["eligible"]]
    rng = np.random.default_rng(seed)
    rows = []
    for scope, g in [("all", el), *el.groupby("scenario")]:
        w = warns if scope == "all" else warns[warns["scenario"] == scope]
        r = runs if scope == "all" else runs[runs["scenario"] == scope]
        leads = g.loc[g["warned"], "lead_s"]
        ci = _boot(g, lambda x: _share(x, "warned"), rng)
        rows.append(
            {
                "scope": scope,
                "seeds": int(r["seed"].nunique()),
                "true_rings": int(r["true_rings"].sum()),
                "eligible_rings": len(g),
                "warned_before_activation": int(g["warned"].sum()),
                "share_warned": _share(g, "warned"),
                "share_warned_lo": ci[0] if ci else None,
                "share_warned_hi": ci[1] if ci else None,
                "early_warning_only": int(g["early_warned"].sum()),
                "lead_median_s": float(leads.median()) if len(leads) else None,
                "lead_q25_s": float(leads.quantile(0.25)) if len(leads) else None,
                "lead_q75_s": float(leads.quantile(0.75)) if len(leads) else None,
                "first_early_warnings": len(w),
                "false_early_warnings": int((~w["correct"]).sum()) if len(w) else 0,
                "warning_precision": float(w["correct"].mean()) if len(w) else None,
                "false_ew_per_sim_hour": float((~w["correct"]).sum() / r["sim_hours"].sum())
                if len(w) and r["sim_hours"].sum()
                else None,
                "old_metric_before_activation": int(r["old_metric_before_activation"].sum()),
            }
        )
    by_type = []
    for t, g in el.groupby("type"):
        leads = g.loc[g["warned"], "lead_s"]
        enough = len(g) >= MIN_TYPE_RINGS
        by_type.append(
            {
                "type": t,
                "eligible_rings": len(g),
                "warned_before_activation": int(g["warned"].sum()),
                "reported": enough,
                "share_warned": _share(g, "warned") if enough else None,
                "lead_median_s": float(leads.median()) if enough and len(leads) else None,
            }
        )
    tables = {"summary": pd.DataFrame(rows), "by_type": pd.DataFrame(by_type)}
    for name, df in tables.items():
        df.to_csv(d / f"{name}.csv", index=False)
    return tables


def _f(x: Any, d: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "undefined"
    return f"{x:.{d}f}" if isinstance(x, float) else str(x)


def report(results_dir: Path) -> str:
    d = Path(results_dir) / "e11_early_warning"
    s = pd.read_csv(d / "summary.csv")
    t = pd.read_csv(d / "by_type.csv")
    lines = [
        "<!-- generated by `python -m fraudsim.experiments.early_warning_eval --report`; "
        "do not edit by hand -->",
        "",
        "**Warned before activation (eligible rings: activated, with a forming phase); "
        "95% seed-bootstrap interval**",
        "",
        "| Scope | True rings | Eligible | Warned (share) | Early-warning kind only | "
        "Lead median s (IQR) | Old final-member count |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in s.iterrows():
        share = f"{r['warned_before_activation']} ({_f(r['share_warned'])}"
        share += (
            f", {_f(r['share_warned_lo'])} to {_f(r['share_warned_hi'])})"
            if not pd.isna(r["share_warned_lo"])
            else ")"
        )
        lines.append(
            f"| {r['scope']} | {r['true_rings']} | {r['eligible_rings']} | {share} | "
            f"{r['early_warning_only']} | {_f(r['lead_median_s'], 1)} "
            f"({_f(r['lead_q25_s'], 1)} to {_f(r['lead_q75_s'], 1)}) | "
            f"{r['old_metric_before_activation']} |"
        )
    lines += [
        "",
        "**First early warning per tracked ring**",
        "",
        "| Scope | Early warnings | False | Precision | False per simulated h |",
        "|---|---|---|---|---|",
    ]
    for _, r in s.iterrows():
        lines.append(
            f"| {r['scope']} | {r['first_early_warnings']} | {r['false_early_warnings']} | "
            f"{_f(r['warning_precision'])} | {_f(r['false_ew_per_sim_hour'], 1)} |"
        )
    lines += [
        "",
        f"**By ring type (types with < {MIN_TYPE_RINGS} eligible rings: counts only)**",
        "",
        "| Type | Eligible | Warned | Share | Lead median s |",
        "|---|---|---|---|---|",
    ]
    for _, r in t.iterrows():
        lines.append(
            f"| {r['type']} | {r['eligible_rings']} | {r['warned_before_activation']} | "
            f"{_f(r['share_warned']) if r['reported'] else 'n/a'} | "
            f"{_f(r['lead_median_s'], 1) if r['reported'] else 'n/a'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", default="results/")
    ap.add_argument("--report", metavar="PATH", help="write the generated Markdown tables to PATH")
    args = ap.parse_args()
    tables = analyse(Path(args.results_dir))
    if args.report:
        Path(args.report).write_text(report(Path(args.results_dir)), encoding="utf-8")
        print(f"wrote {args.report}")
        return
    with pd.option_context("display.width", 200, "display.max_columns", 40):
        for name, df in tables.items():
            print(f"\n== {name}\n{df.to_string(index=False)}")


if __name__ == "__main__":
    main()
