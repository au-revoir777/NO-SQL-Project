"""
E10 analysis: ring-level calibration, precision/lift at the top k%, alert
burden, and a calibrator comparison, from results/e10_ring_alerts/units.csv.

Every definition (unit, label, cutoffs, bins, splits, bootstrap) is fixed in
docs/research/e10_protocol.md; this module only implements it.

    python -m fraudsim.experiments.ring_calibration --results-dir results/
"""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from fraudsim.scoring.scorer import RingScorer

K_PERCENTS = (1, 5, 10)
N_BINS = 10
BOOTSTRAP = 2000
MIN_TYPE_UNITS = 20
ECE_MIN_UNITS = 100
EPS = 1e-6


# ─── Metric primitives (each tested in tests/test_ring_calibration.py) ────────


def precision_at(scores: np.ndarray, labels: np.ndarray, k_pct: float) -> float | None:
    """
    Share of positives in the top ceil(k% * n) by score; None when n = 0.

    Tie-aware (protocol amendment 1): units tied with the score at the cutoff
    contribute their group's positive rate, i.e. the expected precision over
    all orders of the tied units, so the result never depends on input order.
    """
    n = len(scores)
    if n == 0:
        return None
    top = max(1, math.ceil(k_pct / 100.0 * n))
    cut = np.sort(scores)[::-1][top - 1]
    above = scores > cut
    tied = scores == cut
    taken_from_ties = top - int(above.sum())
    positives = float(labels[above].sum()) + taken_from_ties * float(labels[tied].mean())
    return positives / top


def lift_at(scores: np.ndarray, labels: np.ndarray, k_pct: float) -> float | None:
    """precision@k / base rate; None (undefined) when n = 0 or the base rate is 0."""
    p = precision_at(scores, labels, k_pct)
    base = float(labels.mean()) if len(labels) else 0.0
    if p is None or base == 0.0:
        return None
    return p / base


def brier(scores: np.ndarray, labels: np.ndarray) -> float | None:
    return float(np.mean((scores - labels) ** 2)) if len(scores) else None


def reliability(
    scores: np.ndarray, labels: np.ndarray, bins: int = N_BINS, mode: str = "width"
) -> list[dict[str, Any]]:
    """Bins of equal width on [0, 1], or equal mass (quantiles); empty bins are dropped."""
    if not len(scores):
        return []
    if mode == "width":
        idx = np.minimum((scores * bins).astype(int), bins - 1)
    else:
        order = np.argsort(scores, kind="stable")
        idx = np.empty(len(scores), dtype=int)
        idx[order] = np.arange(len(scores)) * bins // len(scores)
    rows = []
    for b in range(bins):
        m = idx == b
        if m.any():
            rows.append(
                {
                    "bin": b,
                    "n": int(m.sum()),
                    "mean_score": float(scores[m].mean()),
                    "positive_rate": float(labels[m].mean()),
                }
            )
    return rows


def ece(
    scores: np.ndarray, labels: np.ndarray, bins: int = N_BINS, mode: str = "width"
) -> float | None:
    rows = reliability(scores, labels, bins, mode)
    n = len(scores)
    if not n:
        return None
    return float(sum(r["n"] / n * abs(r["positive_rate"] - r["mean_score"]) for r in rows))


# ─── Calibrators ──────────────────────────────────────────────────────────────


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def fit_calibrators(
    cal: pd.DataFrame, scorer: RingScorer
) -> dict[str, Callable[[np.ndarray], np.ndarray]]:
    """Candidates of the protocol; the refits use calibration-seed units only."""
    raw, y = cal["raw"].to_numpy(float), cal["y"].to_numpy(int)
    out: dict[str, Callable[[np.ndarray], np.ndarray]] = {
        "shipped": lambda r: np.clip(scorer.calibrator.predict(r), 0.0, 1.0),  # type: ignore[union-attr]
        "uncalibrated": lambda r: r,
    }
    if len(set(y.tolist())) == 2:
        platt = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(raw).reshape(-1, 1), y)
        out["platt_ring"] = lambda r: platt.predict_proba(_logit(r).reshape(-1, 1))[:, 1]
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(raw, y)
        out["isotonic_ring"] = lambda r: np.clip(iso.predict(r), 0.0, 1.0)
    return out


# ─── Aggregation with a seed-cluster bootstrap ────────────────────────────────


def _metrics(df: pd.DataFrame, score_col: str, threshold: float | None) -> dict[str, Any]:
    s, y = df[score_col].to_numpy(float), df["y"].to_numpy(int)
    m: dict[str, Any] = {
        "units": len(df),
        "tp": int((df["label"] == "tp").sum()),
        "duplicate": int((df["label"] == "duplicate").sum()),
        "fp": int((df["label"] == "fp").sum()),
        "base_rate": float(y.mean()) if len(y) else None,
        "brier": brier(s, y),
        "ece_width": ece(s, y, mode="width"),
        "ece_mass": ece(s, y, mode="mass"),
    }
    for k in K_PERCENTS:
        m[f"precision_at_{k}pct"] = precision_at(s, y, k)
        m[f"lift_at_{k}pct"] = lift_at(s, y, k)
    if threshold is not None:
        alert = s >= threshold
        m["alerts"] = int(alert.sum())
        m["alerts_tp"] = int(((df["label"] == "tp") & alert).sum())
        m["alerts_duplicate"] = int(((df["label"] == "duplicate") & alert).sum())
        m["alerts_fp"] = int(((df["label"] == "fp") & alert).sum())
    return m


def _bootstrap(
    df: pd.DataFrame,
    score_col: str,
    keys: list[str],
    rng: np.random.Generator,
    n: int = BOOTSTRAP,
) -> dict[str, tuple[float, float]]:
    """95% percentile intervals; seeds resampled with replacement within each scenario."""
    groups = {k: g for k, g in df.groupby(["scenario", "seed"])}
    by_scenario: dict[str, list[pd.DataFrame]] = {}
    for (scenario, _), g in groups.items():
        by_scenario.setdefault(scenario, []).append(g)
    draws: dict[str, list[float]] = {k: [] for k in keys}
    for _ in range(n):
        parts = []
        for runs in by_scenario.values():
            pick = rng.integers(0, len(runs), len(runs))
            parts.extend(runs[i] for i in pick)
        sample = pd.concat(parts, ignore_index=True)
        m = _metrics(sample, score_col, None)
        for k in keys:
            if m.get(k) is not None:
                draws[k].append(m[k])
    return {
        k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)))
        for k, v in draws.items()
        if len(v) >= n // 2  # undefined in too many resamples: no interval
    }


def analyse(results_dir: Path, seed: int = 0) -> dict[str, pd.DataFrame]:
    """Compute summary, calibrator comparison and reliability tables; write them as CSV."""
    from fraudsim.experiments.harness import DEFAULT_MODEL
    from fraudsim.experiments.tuning import load_tuned

    out_dir = Path(results_dir) / "e10_ring_alerts"
    units = pd.read_csv(out_dir / "units.csv")
    runs = pd.read_csv(out_dir / "results.csv")
    units["y"] = (units["label"] == "tp").astype(int)
    scorer = RingScorer.load(DEFAULT_MODEL)
    threshold = float((load_tuned() or {}).get("alert_threshold", 0.5))
    cal, test = units[units["split"] == "calibration"], units[units["split"] == "test"]
    calibrators = fit_calibrators(cal, scorer)
    for name, f in calibrators.items():
        test = test.assign(**{name: f(test["raw"].to_numpy(float))})
    rng = np.random.default_rng(seed)
    keys = ["brier", "ece_width", "precision_at_1pct", "precision_at_5pct",
            "precision_at_10pct", "lift_at_5pct", "lift_at_10pct"]  # fmt: skip

    hours = runs[runs["split"] == "test"].groupby("scenario")["sim_hours"].sum()
    summary_rows, cal_rows, rel_rows = [], [], []
    scopes: list[tuple[str, pd.DataFrame]] = [("all", test)] + [
        (s, g) for s, g in test.groupby("scenario")
    ]
    for scope, g in scopes:
        h = float(hours.sum() if scope == "all" else hours.get(scope, 0.0))
        m = _metrics(g, "shipped", threshold)
        ci = _bootstrap(g, "shipped", keys, rng)
        row = {"scope": scope, "seeds": g["seed"].nunique(), "sim_hours": h,
               "alerts_per_sim_hour": m["alerts"] / h if h else None, **m}  # fmt: skip
        for k, (lo, hi) in ci.items():
            row[f"{k}_lo"], row[f"{k}_hi"] = lo, hi
        row["ece_interpretable"] = len(g) >= ECE_MIN_UNITS
        summary_rows.append(row)
        for name in calibrators:
            cm = _metrics(g, name, None)
            cci = _bootstrap(g, name, ["brier", "ece_width"], np.random.default_rng(seed))
            cal_rows.append(
                {
                    "scope": scope,
                    "calibrator": name,
                    "units": cm["units"],
                    "brier": cm["brier"],
                    "ece_width": cm["ece_width"],
                    "ece_mass": cm["ece_mass"],
                    **{
                        f"{k}_{b}": v
                        for k, (lo, hi) in cci.items()
                        for b, v in (("lo", lo), ("hi", hi))
                    },
                }
            )
            if scope == "all":
                for mode in ("width", "mass"):
                    for r in reliability(g[name].to_numpy(float), g["y"].to_numpy(int), mode=mode):
                        rel_rows.append({"calibrator": name, "binning": mode, **r})
    by_type = []
    for t, g in test.groupby("ring_type"):
        m = _metrics(g, "shipped", threshold)
        enough = len(g) >= MIN_TYPE_UNITS
        by_type.append(
            {
                "ring_type": t,
                "units": m["units"],
                "tp": m["tp"],
                "duplicate": m["duplicate"],
                "fp": m["fp"],
                "reported": enough,
                **(
                    {
                        k: m[k]
                        for k in (
                            "base_rate",
                            "brier",
                            "precision_at_10pct",
                            "lift_at_10pct",
                            "alerts",
                            "alerts_tp",
                            "alerts_fp",
                        )
                    }
                    if enough
                    else {}
                ),
            }
        )
    tables = {
        "summary": pd.DataFrame(summary_rows),
        "calibrators": pd.DataFrame(cal_rows),
        "reliability": pd.DataFrame(rel_rows),
        "by_type": pd.DataFrame(by_type),
    }
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    return tables


def _fmt(x: Any, d: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "undefined"
    return f"{x:.{d}f}" if isinstance(x, float) else str(x)


def _ci(row: pd.Series, k: str, d: int = 3) -> str:
    lo, hi = row.get(f"{k}_lo"), row.get(f"{k}_hi")
    if lo is None or hi is None or (isinstance(lo, float) and math.isnan(lo)):
        return _fmt(row.get(k), d)
    return f"{_fmt(row.get(k), d)} ({_fmt(lo, d)} to {_fmt(hi, d)})"


def report(results_dir: Path) -> str:
    """Markdown tables generated from the E10 CSVs (no number typed by hand)."""
    d = Path(results_dir) / "e10_ring_alerts"
    s = pd.read_csv(d / "summary.csv")
    c = pd.read_csv(d / "calibrators.csv")
    t = pd.read_csv(d / "by_type.csv")
    runs = pd.read_csv(d / "results.csv")
    test = runs[runs["split"] == "test"]
    lines = [
        "<!-- generated by `python -m fraudsim.experiments.ring_calibration --report`; "
        "do not edit by hand -->",
        "",
        f"Test runs: {len(test)} ({test['scenario'].nunique()} scenarios x "
        f"{test['seed'].nunique()} seeds); true rings {int(test['true_rings'].sum())}; "
        f"eligible units {int(test['eligible_units'].sum())}, not eligible "
        f"{int(test['not_eligible_units'].sum())}.",
        "",
        "**Alert utility (shipped calibrator); 95% seed-bootstrap intervals in brackets**",
        "",
        "| Scope | Units | tp / dup / fp | Base rate | P@1% | P@5% | P@10% | Lift@5% | Lift@10% |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for _, r in s.iterrows():
        lines.append(
            f"| {r['scope']} | {r['units']} | {r['tp']} / {r['duplicate']} / {r['fp']} | "
            f"{_fmt(r['base_rate'])} | {_ci(r, 'precision_at_1pct')} | "
            f"{_ci(r, 'precision_at_5pct')} | {_ci(r, 'precision_at_10pct')} | "
            f"{_ci(r, 'lift_at_5pct', 2)} | {_ci(r, 'lift_at_10pct', 2)} |"
        )
    lines += [
        "",
        "**Alert burden at the operating threshold (shipped calibrator)**",
        "",
        "| Scope | Simulated h | Alerts | tp | dup | fp | Alerts / simulated h |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in s.iterrows():
        lines.append(
            f"| {r['scope']} | {_fmt(r['sim_hours'], 2)} | {r['alerts']} | {r['alerts_tp']} | "
            f"{r['alerts_duplicate']} | {r['alerts_fp']} | {_fmt(r['alerts_per_sim_hour'], 1)} |"
        )
    lines += [
        "",
        "**Calibration by calibrator (test seeds); ECE with 10 equal-width bins**",
        "",
        "| Scope | Calibrator | Brier | ECE | ECE (equal mass) |",
        "|---|---|---|---|---|",
    ]
    for _, r in c.iterrows():
        lines.append(
            f"| {r['scope']} | {r['calibrator']} | {_ci(r, 'brier')} | "
            f"{_ci(r, 'ece_width')} | {_fmt(r['ece_mass'])} |"
        )
    lines += [
        "",
        "**By tracked-ring type (shipped calibrator; types with < 20 units: counts only)**",
        "",
        "| Type | Units | tp / dup / fp | Base rate | P@10% | Alerts (tp / fp) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in t.iterrows():
        extra = (
            f"{_fmt(r['base_rate'])} | {_fmt(r['precision_at_10pct'])} | "
            f"{int(r['alerts'])} ({int(r['alerts_tp'])} / {int(r['alerts_fp'])})"
            if bool(r["reported"])
            else "n/a | n/a | n/a"
        )
        counts = f"{r['tp']} / {r['duplicate']} / {r['fp']}"
        lines.append(f"| {r['ring_type']} | {r['units']} | {counts} | {extra} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", default="results/")
    ap.add_argument(
        "--report", metavar="PATH", help="only write the generated Markdown tables to PATH"
    )
    args = ap.parse_args()
    if args.report:
        Path(args.report).write_text(report(Path(args.results_dir)), encoding="utf-8")
        print(f"wrote {args.report}")
        return
    tables = analyse(Path(args.results_dir))
    with pd.option_context("display.width", 200, "display.max_columns", 40):
        for name, df in tables.items():
            print(f"\n== {name}\n{df.to_string(index=False)}")


if __name__ == "__main__":
    main()
