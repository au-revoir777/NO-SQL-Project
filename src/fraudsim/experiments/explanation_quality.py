"""
E12: explanation quality, as fixed in docs/research/e12_protocol.md.

    python -m fraudsim.experiments.explanation_quality --collect --results-dir results
    python -m fraudsim.experiments.explanation_quality --analyse --results-dir results \
        --retrained results/e12_explanations/retrained_scorer_lr_seeds111-120.joblib
    python -m fraudsim.experiments.explanation_quality --report docs/research/e12_tables.md

Collection re-runs E10's test streams and stores each unit's features and
members at its peak; analysis reads only units.csv and the two scorers. The
metric primitives below are unit-tested on hand-made inputs.
"""

from __future__ import annotations

import argparse
import json
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fraudsim.experiments.alert_units import SCENARIOS, label_units, peak_events, run_scored
from fraudsim.experiments.harness import _append, make_stream
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.logging.replay import file_sha256
from fraudsim.metrics.evaluation import all_members, true_rings
from fraudsim.scoring.explanations import ACTIONABLE, model_counterfactuals
from fraudsim.scoring.features import FEATURE_NAMES
from fraudsim.scoring.scorer import RingScorer

EXPERIMENT = "e12_explanations"
THRESHOLD = 0.8
TEST_SEEDS = tuple(range(1001, 1011))
DELTAS = (0.01, 0.05)
K_DRAWS = 20
TOP = 3
NON_ACTIONABLE = tuple(f for f in FEATURE_NAMES if f not in ACTIONABLE)
ORACLE = "Oracle (simulator ground truth)"
DASH = chr(0x2013)  # en dash for empty table cells


# ─── Metric primitives (tests/test_explanation_quality.py) ────────────────────


def contribution_vector(contrib: dict[str, float]) -> np.ndarray:
    return np.asarray([contrib[f] for f in FEATURE_NAMES], dtype=float)


def contribution_drift(c0: np.ndarray, c1: np.ndarray) -> float:
    """||c1 - c0||_1 / ||c0||_1 (0 when c0 is all zero and c1 equals it)."""
    denom = float(np.abs(c0).sum())
    diff = float(np.abs(c1 - c0).sum())
    if denom == 0.0:
        return 0.0 if diff == 0.0 else float("inf")
    return diff / denom


def top_features(contrib: dict[str, float], k: int = TOP) -> set[str]:
    """The k features with the largest |contribution| (ties by feature order)."""
    order = sorted(FEATURE_NAMES, key=lambda f: (-abs(contrib[f]), FEATURE_NAMES.index(f)))
    return set(order[:k])


def jaccard_sets(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def perturb(x: np.ndarray, delta: float, rng: np.random.Generator) -> np.ndarray:
    """Multiply every non-actionable feature by (1 + u), u ~ U(-delta, delta)."""
    out = x.copy()
    for f in NON_ACTIONABLE:
        i = FEATURE_NAMES.index(f)
        out[i] = x[i] * (1.0 + rng.uniform(-delta, delta))
    return out


def unit_rng(scenario: str, seed: int, ring_id: str, delta: float) -> np.random.Generator:
    key = f"{scenario}|{seed}|{ring_id}|{delta}".encode()
    return np.random.default_rng(zlib.crc32(key))


def check_counterfactual(
    scorer: RingScorer, x: np.ndarray, feature: str, target: float, threshold: float = THRESHOLD
) -> tuple[bool, float]:
    """Apply the single-feature change and re-score: (valid, new calibrated score)."""
    y = x.copy()
    y[FEATURE_NAMES.index(feature)] = target
    score = float(scorer.predict(y)[0])
    return score < threshold, score


def fidelity(members: set[str], true_members: set[str]) -> tuple[float, float]:
    """(precision |M & T| / |M|, coverage |M & T| / |T|)."""
    inter = len(members & true_members)
    return (
        inter / len(members) if members else 0.0,
        inter / len(true_members) if true_members else 0.0,
    )


def same_first(
    first: tuple[str, float, float] | None, other: list[tuple[str, float, float]]
) -> bool:
    """Both propose no counterfactual, or both propose the same first feature."""
    if first is None:
        return not other
    return bool(other) and other[0][0] == first[0]


def spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if np.allclose(a, a[0]) or np.allclose(b, b[0]):
        return None
    rho = spearmanr(a, b).statistic
    return float(rho)


# ─── Collection ───────────────────────────────────────────────────────


def collect(
    out: Path,
    test_seeds: Sequence[int] = TEST_SEEDS,
    scenarios: Sequence[str] = SCENARIOS,
    model_path: Path | None = None,
    log: Callable[[str], None] = print,
) -> Path:
    """Re-run E10's test streams; one row per unit with features and members at the peak."""
    from fraudsim.experiments.harness import DEFAULT_MODEL
    from fraudsim.experiments.suite import tuned_proposed

    model_path = Path(model_path or DEFAULT_MODEL)
    scorer = RingScorer.load(model_path)
    method = tuned_proposed()
    out_dir = Path(out) / EXPERIMENT
    details = {
        "protocol": "docs/research/e12_protocol.md",
        "method": method.config() | {"label": method.label},
        "scenarios": list(scenarios),
        "test_seeds": list(test_seeds),
        "model": {"path": repo_relative(model_path), "sha256": file_sha256(model_path)},
        "alert_threshold": THRESHOLD,
    }
    with recorded(out_dir, EXPERIMENT, details):
        for scenario in scenarios:
            for seed in test_seeds:
                stream = make_stream(scenario, seed, None)
                engine, stage = run_scored(stream, method, scorer, record=True)
                gen = stream.generator
                start_t = gen.ts(0.0).timestamp()
                truth_rings = true_rings(gen.ledger)
                truth = {r.ring_id: all_members(r) for r in truth_rings}
                all_true = set().union(*truth.values()) if truth else set()
                events, _ = peak_events(stage.rows, scorer)
                for u in label_units(events, truth):
                    ev = u["event"]
                    members = set(ev.members)
                    tm = truth.get(u["true_ring"]) if u["true_ring"] else None
                    prec, cov = fidelity(members, tm) if tm else (None, None)
                    _append(
                        out_dir / "units.csv",
                        {
                            "scenario": scenario,
                            "seed": seed,
                            "ring_id": ev.ring_id,
                            "ring_type": engine.tracker.rings[ev.ring_id].ring_type.value,
                            "peak_t_s": round(ev.t - start_t, 3),
                            "shipped": round(ev.shipped, 8),
                            "label": u["label"],
                            "true_ring": u["true_ring"] or "",
                            "members": json.dumps(sorted(members)),
                            "true_size": len(tm) if tm else "",
                            "evidence_precision": round(prec, 6) if prec is not None else "",
                            "evidence_coverage": round(cov, 6) if cov is not None else "",
                            "share_in_any_true_ring": round(
                                len(members & all_true) / len(members), 6
                            ),
                            "features": json.dumps(list(ev.features)),
                            "stream_digest": gen.digest[:16],
                        },
                    )
                _append(
                    out_dir / "results.csv",
                    {
                        "scenario": scenario,
                        "seed": seed,
                        "stream_digest": gen.digest[:16],
                        "events": len(stream.events),
                        "units": len(events),
                        "alerts": sum(1 for e in events if e.shipped >= THRESHOLD),
                    },
                )
                log(f"[e12] {scenario} seed={seed} units={len(events)}")
    return out_dir


# ─── Analysis ─────────────────────────────────────────────────────────


def analyse(
    results_dir: Path,
    retrained_path: Path,
    model_path: Path | None = None,
    log: Callable[[str], None] = print,
) -> Path:
    """Counterfactuals, stability and consistency over alerts; writes CSVs next to units.csv."""
    from fraudsim.experiments.harness import DEFAULT_MODEL

    out_dir = Path(results_dir) / EXPERIMENT
    units = pd.read_csv(out_dir / "units.csv")
    model_path = Path(model_path or DEFAULT_MODEL)
    a = RingScorer.load(model_path)
    b = RingScorer.load(retrained_path)
    x_all = np.asarray([json.loads(s) for s in units["features"]], dtype=float)
    std = x_all.std(axis=0)
    lo, hi = x_all.min(axis=0), x_all.max(axis=0)
    alerts = units[units["shipped"] >= THRESHOLD]
    cf_rows: list[dict[str, Any]] = []
    stab_rows: list[dict[str, Any]] = []
    cons_rows: list[dict[str, Any]] = []
    for _, u in alerts.iterrows():
        x = np.asarray(json.loads(u["features"]), dtype=float)
        key = {"scenario": u["scenario"], "seed": int(u["seed"]), "ring_id": u["ring_id"]}
        ca = a.contributions(x)
        score = float(a.predict(x)[0])
        cfs = model_counterfactuals(a, x, ca, THRESHOLD)
        modes = (
            ("as_shipped", model_counterfactuals(a, x, ca, THRESHOLD, exact_crossing=False)),
            ("corrected", cfs),
        )
        for mode, mode_cfs in modes:
            for rank, (feat, cur, tgt) in enumerate(mode_cfs, start=1):
                i = FEATURE_NAMES.index(feat)
                valid, new = check_counterfactual(a, x, feat, tgt)
                cf_rows.append(
                    key
                    | {
                        "mode": mode,
                        "rank": rank,
                        "feature": feat,
                        "current": round(cur, 6),
                        "target": round(tgt, 6),
                        "valid": valid,
                        "in_range": bool(lo[i] <= tgt <= hi[i]),
                        "relative_change": round(abs(tgt - cur) / std[i], 6) if std[i] else "",
                        "score": round(score, 6),
                        "new_score": round(new, 6),
                        "score_drop": round(score - new, 6),
                    }
                )
        first = cfs[0] if cfs else None
        c0 = contribution_vector(ca)
        t0 = top_features(ca)
        for delta in DELTAS:
            rng = unit_rng(str(u["scenario"]), int(u["seed"]), str(u["ring_id"]), delta)
            drifts, tops, same_cf, tdrift = [], [], [], []
            for _ in range(K_DRAWS):
                xp = perturb(x, delta, rng)
                cp = a.contributions(xp)
                drifts.append(contribution_drift(c0, contribution_vector(cp)))
                tops.append(jaccard_sets(t0, top_features(cp)))
                cfp = model_counterfactuals(a, xp, cp, THRESHOLD)
                same_cf.append(same_first(first, cfp))
                if first is not None:
                    i = FEATURE_NAMES.index(first[0])
                    tp = a.counterfactual_value(xp, first[0], THRESHOLD)
                    if tp is not None and std[i]:
                        tdrift.append(abs(tp - first[2]) / std[i])
            stab_rows.append(
                key
                | {
                    "delta": delta,
                    "contribution_drift": round(float(np.mean(drifts)), 6),
                    "top3_agreement": round(float(np.mean(tops)), 6),
                    "cf_agreement": round(float(np.mean(same_cf)), 6),
                    "target_drift": round(float(np.mean(tdrift)), 6) if tdrift else "",
                }
            )
        cb = b.contributions(x)
        cfs_b = model_counterfactuals(b, x, cb, THRESHOLD)
        rho = spearman(c0, contribution_vector(cb))
        cons_rows.append(
            key
            | {
                "ring_type": u["ring_type"],
                "label": u["label"],
                "spearman": round(rho, 6) if rho is not None else "",
                "top3_agreement": round(jaccard_sets(t0, top_features(cb)), 6),
                "cf_agreement": same_first(first, cfs_b),
                "retrained_score": round(float(b.predict(x)[0]), 6),
                "retrained_alerts": bool(float(b.predict(x)[0]) >= THRESHOLD),
                "contributions": json.dumps({f: round(ca[f], 6) for f in FEATURE_NAMES}),
            }
        )
    for name, rows in (
        ("counterfactuals", cf_rows),
        ("stability", stab_rows),
        ("consistency", cons_rows),
    ):
        pd.DataFrame(rows).to_csv(out_dir / f"{name}.csv", index=False)
    manifest_path = out_dir / "analysis.json"
    manifest_path.write_text(
        json.dumps(
            {
                "protocol": "docs/research/e12_protocol.md",
                "units": len(units),
                "alerts": len(alerts),
                "threshold": THRESHOLD,
                "deltas": list(DELTAS),
                "draws": K_DRAWS,
                "shipped_model": {
                    "path": repo_relative(model_path),
                    "sha256": file_sha256(model_path),
                },
                "retrained_model": {
                    "path": repo_relative(Path(retrained_path)),
                    "sha256": file_sha256(Path(retrained_path)),
                    "train_seeds": b.meta.train.get("train_seeds"),
                    "training_id": b.meta.train.get("training_id"),
                },
                "units_sha256": file_sha256(out_dir / "units.csv"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"[e12] alerts={len(alerts)} counterfactuals={len(cf_rows)}")
    return out_dir


# ─── Report ───────────────────────────────────────────────────────────


def _q(s: pd.Series) -> str:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return DASH
    return f"{s.median():.3f} [{s.quantile(0.25):.3f}, {s.quantile(0.75):.3f}]"


def _rate(s: pd.Series) -> str:
    s = s.dropna()
    if s.empty:
        return DASH
    return f"{s.astype(bool).mean():.3f} ({int(s.astype(bool).sum())}/{len(s)})"


def report(results_dir: Path, out: Path) -> Path:
    d = Path(results_dir) / EXPERIMENT
    units = pd.read_csv(d / "units.csv")
    cf = pd.read_csv(d / "counterfactuals.csv")
    stab = pd.read_csv(d / "stability.csv")
    cons = pd.read_csv(d / "consistency.csv")
    alerts = units[units["shipped"] >= THRESHOLD]
    lines = [
        "# E12 tables (generated)",
        "",
        "Generated by `python -m fraudsim.experiments.explanation_quality --report "
        "docs/research/e12_tables.md` from `results/e12_explanations/`. Do not edit by hand.",
        "Cells are median [IQR] unless marked as a rate (share, with counts).",
        "",
        "## Units and alerts",
        "",
        "| Scenario | Units | Alerts (score ≥ 0.8) | Alerts tp | Alerts duplicate | Alerts fp |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sc, g in units.groupby("scenario", sort=True):
        ga = g[g["shipped"] >= THRESHOLD]
        lines.append(
            f"| {sc} | {len(g)} | {len(ga)} | {(ga['label'] == 'tp').sum()} | "
            f"{(ga['label'] == 'duplicate').sum()} | {(ga['label'] == 'fp').sum()} |"
        )
    lines.append(
        f"| all | {len(units)} | {len(alerts)} | {(alerts['label'] == 'tp').sum()} | "
        f"{(alerts['label'] == 'duplicate').sum()} | {(alerts['label'] == 'fp').sum()} |"
    )
    lines += [
        "",
        "## Counterfactual validity by computation (protocol amendment 1)",
        "",
        "as_shipped = the product before E12 (target at the isotonic breakpoint); "
        "corrected = target below the interpolated crossing (the product now).",
        "",
        "| Computation | Alerts with a counterfactual | Counterfactuals | Valid (rate) | "
        "First counterfactual valid (rate) |",
        "|---|---:|---:|---:|---:|",
    ]
    for mode, g in cf.groupby("mode", sort=True):
        n_alerts = g.drop_duplicates(["scenario", "seed", "ring_id"]).shape[0]
        lines.append(
            f"| {mode} | {n_alerts} of {len(alerts)} | {len(g)} | {_rate(g['valid'])} | "
            f"{_rate(g[g['rank'] == 1]['valid'])} |"
        )
    cf = cf[cf["mode"] == "corrected"]
    n_none = len(alerts) - cf.drop_duplicates(["scenario", "seed", "ring_id"]).shape[0]
    lines += [
        "",
        "## Counterfactuals per feature (corrected computation; alerts)",
        "",
        f"Alerts with no model counterfactual: {n_none} of {len(alerts)}.",
        "",
        "| Feature | Counterfactuals | First choice | Valid (rate) | In range (rate) | "
        "Relative change | Score drop |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for feat, g in cf.groupby("feature", sort=True):
        lines.append(
            f"| {feat} | {len(g)} | {(g['rank'] == 1).sum()} | {_rate(g['valid'])} | "
            f"{_rate(g['in_range'])} | {_q(g['relative_change'])} | {_q(g['score_drop'])} |"
        )
    lines.append(
        f"| all | {len(cf)} | {(cf['rank'] == 1).sum()} | {_rate(cf['valid'])} | "
        f"{_rate(cf['in_range'])} | {_q(cf['relative_change'])} | {_q(cf['score_drop'])} |"
    )
    lines += [
        "",
        "## Stability under non-actionable noise (alerts; mean over 20 draws per alert)",
        "",
        "| Noise δ | Alerts | Contribution drift | Top-3 agreement | "
        "First-counterfactual agreement | Target drift (SD units) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for delta, g in stab.groupby("delta", sort=True):
        lines.append(
            f"| {delta:g} | {len(g)} | {_q(g['contribution_drift'])} | {_q(g['top3_agreement'])} | "
            f"{_q(g['cf_agreement'])} | {_q(g['target_drift'])} |"
        )
    lines += [
        "",
        "## Consistency after retraining on seeds 111-120 (alerts of the shipped scorer)",
        "",
        "| Scenario | Alerts | Spearman (contributions) | Top-3 agreement | "
        "First counterfactual same (rate) | Retrained scorer also alerts (rate) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sc, g in cons.groupby("scenario", sort=True):
        lines.append(
            f"| {sc} | {len(g)} | {_q(g['spearman'])} | {_q(g['top3_agreement'])} | "
            f"{_rate(g['cf_agreement'])} | {_rate(g['retrained_alerts'])} |"
        )
    lines.append(
        f"| all | {len(cons)} | {_q(cons['spearman'])} | {_q(cons['top3_agreement'])} | "
        f"{_rate(cons['cf_agreement'])} | {_rate(cons['retrained_alerts'])} |"
    )
    lines += [
        "",
        f"## Evidence fidelity — {ORACLE}",
        "",
        "Precision = share of evidence members in the matched true ring; coverage = share of the "
        "true ring's members in the evidence (tp and duplicate units). "
        "In any true ring = share of evidence members who belong to some true ring (all units).",
        "",
        "| Population | Label | Units | Precision | Coverage | In any true ring |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for pop, df in (("all units", units), ("alerts", alerts)):
        for lab, g in df.groupby("label", sort=True):
            lines.append(
                f"| {pop} | {lab} | {len(g)} | {_q(g['evidence_precision'])} | "
                f"{_q(g['evidence_coverage'])} | {_q(g['share_in_any_true_ring'])} |"
            )
    contrib = pd.DataFrame([json.loads(s) for s in cons["contributions"]], index=cons.index).abs()
    contrib["ring_type"] = cons["ring_type"].to_numpy()
    lines += [
        "",
        "## Semi-global view: mean |contribution| per ring type (alerts; top 5 features)",
        "",
        "| Ring type | Alerts | Top features by mean |contribution| (share of alerts with it in "
        "their top 3) |",
        "|---|---:|---|",
    ]
    for rt, g in contrib.groupby("ring_type", sort=True):
        means = g.drop(columns="ring_type").mean().sort_values(ascending=False).head(5)
        tops = cons.loc[g.index, "contributions"].map(lambda s: top_features(json.loads(s)))
        cells = ", ".join(
            f"{f} {v:.2f} ({tops.map(lambda t, f=f: f in t).mean():.2f})" for f, v in means.items()
        )
        lines.append(f"| {rt} | {len(g)} | {cells} |")
    out = Path(out)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--results-dir", type=Path, default=Path("results"))
    p.add_argument("--collect", action="store_true")
    p.add_argument("--analyse", action="store_true")
    p.add_argument("--retrained", type=Path)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    if args.collect:
        collect(args.results_dir)
    if args.analyse:
        if args.retrained is None:
            p.error("--analyse needs --retrained")
        analyse(args.results_dir, args.retrained)
    if args.report:
        report(args.results_dir, args.report)


if __name__ == "__main__":
    main()
