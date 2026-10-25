"""
E1b (baselines with the shipped calibrated scorer) and E3b (bootstrap intervals
for the frontier experiment), as fixed in docs/research/e1b_protocol.md.

    python -m fraudsim.experiments.scored_baselines tune     # alert threshold per method
    python -m fraudsim.experiments.scored_baselines e1b      # test seeds 1001-1010
    python -m fraudsim.experiments.scored_baselines e3b      # frontier intervals (no new runs)
    python -m fraudsim.experiments.scored_baselines report   # docs/research/e1b_tables.md
"""

# ruff: noqa: RUF001  (tables use typographic dashes and signs)

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fraudsim.experiments.harness import ROOT, Method, baseline_methods, run_grid
from fraudsim.experiments.learned_baselines import paired
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.experiments.stats import fmt_ci, paired_vs, summarize

ACCURACY_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
VALIDATION_SEEDS = (301, 302, 303)
TEST_SEEDS = tuple(range(1001, 1011))
ALERT_GRID = (0.2, 0.3, 0.5, 0.7, 0.8, 0.9)
APRIORI = 0.5
SCORED_OF = {
    "static_cap10": "Cypher cap 10",
    "static_cap100": "Cypher cap 100",
    "louvain": "Louvain",
}
SELECTION = ROOT / "results/e1b_scored_baselines/selected_thresholds.json"
E3B = ROOT / "results/e3b_frontier_ci"
N_BOOT = 2000


def scored(base: str, alert: float, suffix: str = "") -> Method:
    """The E1 baseline `base`, scored by the shipped scorer at alert threshold `alert`."""
    src = next(m for m in baseline_methods() if m.name == base)
    return Method(
        f"{base}_scored{suffix}",
        f"{SCORED_OF[base]} + scorer{suffix and f' (alert {alert})'}",
        {k: dict(v) for k, v in src.overrides.items()},
        scored=True,
        family="baseline_scored",
        alert_threshold=alert,
    )


# ─── Threshold selection (validation seeds only) ──────────────────────────────


def tune(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> dict[str, float]:
    methods = [scored(b, a, f"_a{a}") for b in SCORED_OF for a in ALERT_GRID]
    path = run_grid("e1b_tuning", ACCURACY_SCENARIOS, VALIDATION_SEEDS, methods, Path(out), log=log)
    df = pd.read_csv(path)
    chosen: dict[str, float] = {}
    scores: dict[str, dict[str, float]] = {}
    for b in SCORED_OF:
        s = {
            a: float(df[df["method"] == f"{b}_scored_a{a}"]["f1"].fillna(0).mean())
            for a in ALERT_GRID
        }
        scores[b] = {str(a): round(v, 4) for a, v in s.items()}
        chosen[b] = max(ALERT_GRID, key=lambda a: (s[a], -a))
        log(f"[e1b tune] {b}: alert {chosen[b]} (mean F1 {s[chosen[b]]:.4f})")
    SELECTION.parent.mkdir(parents=True, exist_ok=True)
    SELECTION.write_text(
        json.dumps(
            {
                "alert_threshold": chosen,
                "mean_f1_by_threshold": scores,
                "selected_by": "max mean ring F1 on validation seeds; ties to the lower threshold",
                "validation_seeds": list(VALIDATION_SEEDS),
                "scenarios": list(ACCURACY_SCENARIOS),
                "results": repo_relative(path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return chosen


def selected() -> dict[str, float]:
    return {
        k: float(v)
        for k, v in json.loads(SELECTION.read_text(encoding="utf-8"))["alert_threshold"].items()
    }


def e1b(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    chosen = selected()
    methods = [scored(b, chosen[b]) for b in SCORED_OF]
    methods += [scored(b, APRIORI, "_apriori") for b in SCORED_OF]
    return run_grid(
        "e1b_scored_baselines", ACCURACY_SCENARIOS, TEST_SEEDS, methods, Path(out), log=log
    )


# ─── E3b: bootstrap intervals for the frontier ────────────────────────────────


def _counts(df: pd.DataFrame, method: str, keys: list[tuple[str, int]]) -> np.ndarray:
    sub = df[df["method"] == method].set_index(["scenario", "seed"])
    cols = ["rings_flagged", "false_rings", "true_rings", "rings_detected"]
    return np.array([sub.loc[k, cols].to_numpy(dtype=float) for k in keys])


def _pr(c: np.ndarray) -> tuple[float, float, float]:
    """Micro-averaged precision, recall and F1 from summed run counts (as plotted)."""
    flagged, fp, true, det = c.sum(axis=0)
    p = (flagged - fp) / flagged if flagged else float("nan")
    r = det / true if true else float("nan")
    f = 2 * p * r / (p + r) if flagged and true and (p + r) else 0.0
    return p, r, f


def e3b(log: Callable[[str], None] = print) -> Path:
    src = ROOT / "results/e3_frontier/results.csv"
    df = pd.read_csv(src)
    df["seed"] = df["seed"].astype(int)
    keys = sorted({(s, int(d)) for s, d in zip(df["scenario"], df["seed"], strict=True)})
    by_scen: dict[str, list[int]] = {}
    for i, (s, _) in enumerate(keys):
        by_scen.setdefault(s, []).append(i)
    methods = list(dict.fromkeys(df["method"]))
    fam = dict(zip(df["method"], df["family"], strict=False))
    counts = {m: _counts(df, m, keys) for m in methods}
    rng = np.random.default_rng(0)
    idx = []
    for _ in range(N_BOOT):
        idx.append(
            np.concatenate([rng.choice(v, size=len(v), replace=True) for v in by_scen.values()])
        )
    points: dict[str, Any] = {}
    for m in methods:
        p, r, f = _pr(counts[m])
        boot = np.array([_pr(counts[m][i]) for i in idx])
        lo, hi = np.nanpercentile(boot, 2.5, axis=0), np.nanpercentile(boot, 97.5, axis=0)
        points[m] = {
            "family": fam[m],
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f, 4),
            "precision_ci": [round(lo[0], 4), round(hi[0], 4)],
            "recall_ci": [round(lo[1], 4), round(hi[1], 4)],
            "f1_ci": [round(lo[2], 4), round(hi[2], 4)],
        }

    def best(family: str, sel: np.ndarray | None) -> tuple[str, float]:
        cands = [m for m in methods if fam[m] == family]
        vals = {m: _pr(counts[m] if sel is None else counts[m][sel])[2] for m in cands}
        top = max(cands, key=lambda m: vals[m])
        return top, vals[top]

    hub_m, hub_f = best("hub_scored", None)
    cap_m, cap_f = best("cap_scored", None)
    diffs = np.array([best("hub_scored", i)[1] - best("cap_scored", i)[1] for i in idx])
    per_run = {
        m: (
            df[df["method"] == m]
            .set_index(["scenario", "seed"])
            .loc[keys, "f1"]
            .fillna(0)
            .to_numpy(dtype=float)
        )
        for m in (hub_m, cap_m)
    }
    record = {
        "protocol": "docs/research/e1b_protocol.md (E3b)",
        "source": repo_relative(src),
        "runs_per_point": len(keys),
        "bootstrap": {"resamples": N_BOOT, "seed": 0, "stratified_by": "scenario"},
        "best_f1": {
            "hub_scored": {"method": hub_m, "f1": round(hub_f, 4)},
            "cap_scored": {"method": cap_m, "f1": round(cap_f, 4)},
            "difference": round(hub_f - cap_f, 4),
            "difference_ci": [
                round(float(np.percentile(diffs, 2.5)), 4),
                round(float(np.percentile(diffs, 97.5)), 4),
            ],
            "share_of_resamples_hub_better": round(float((diffs > 0).mean()), 4),
            "per_run_wilcoxon": paired(per_run[hub_m], per_run[cap_m]),
        },
        "points": points,
    }
    E3B.mkdir(parents=True, exist_ok=True)
    out = E3B / "frontier_ci.json"
    with recorded(E3B, "e3b_frontier_ci", {"source": repo_relative(src), "resamples": N_BOOT}):
        out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    d = record["best_f1"]
    log(
        f"[e3b] best F1 hub+S {hub_f:.3f} ({hub_m}) vs cap+S {cap_f:.3f} ({cap_m}); "
        f"diff {d['difference']:+.3f}, 95% CI {d['difference_ci']}"
    )
    return out


# ─── Report ───────────────────────────────────────────────────────────


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values."""
    order = sorted(pvals, key=lambda k: pvals[k])
    m, out, running = len(order), {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvals[k]))
        out[k] = running
    return out


def combined() -> pd.DataFrame:
    """E1 rows plus the scored-baseline rows at their selected thresholds (Table II)."""
    e1 = pd.read_csv(ROOT / "results/e1_baselines/results.csv")
    e1b_df = pd.read_csv(ROOT / "results/e1b_scored_baselines/results.csv")
    return pd.concat([e1, e1b_df], ignore_index=True)


def tests(df: pd.DataFrame) -> pd.DataFrame:
    """paired_vs (the paper's test) against the proposed method, with Holm over the main family."""
    t = paired_vs(df, "proposed", "f1").set_index("method")
    family = [m for m in MAIN_FAMILY if m in t.index]
    adj = holm({m: float(t.loc[m, "wilcoxon_p"]) for m in family})
    t["holm_p"] = [adj.get(m, float("nan")) for m in t.index]
    return t


MAIN_FAMILY = (
    "static_cap100",
    "static_cap10",
    "louvain",
    "plain_cc",
    "proposed_default",
    "static_cap100_scored",
    "static_cap10_scored",
    "louvain_scored",
)


def report(out_md: Path = ROOT / "docs/research/e1b_tables.md") -> None:
    df = combined()
    s = summarize(df, ["method"]).set_index("method")
    t = tests(df)
    sel = selected()
    secondary = [f"{b}_scored_apriori" for b in SCORED_OF]
    keys = df[df["method"] == "proposed"][["scenario", "seed"]].drop_duplicates()

    def fmt_p(p: float) -> str:
        return "<0.001" if p < 0.001 else f"{p:.3f}"

    label = {
        "static_cap100": "Static Cypher (cap 100)",
        "static_cap10": "Static Cypher (cap 10)",
        "louvain": "Louvain communities",
        "plain_cc": "Connected components",
        "proposed_default": "Proposed, a-priori thresholds",
        "proposed": "Hub-aware incremental (proposed)",
    }
    for b in SCORED_OF:
        label[f"{b}_scored"] = f"{label[b]} + scorer (alert {sel[b]})"
        label[f"{b}_scored_apriori"] = f"{label[b]} + scorer (alert {APRIORI})"

    def row(m: str, p_col: str) -> str:
        r = s.loc[m]
        cells = [fmt_ci(r[f"{c}_mean"], r[f"{c}_ci95"]) for c in ("precision", "recall", "f1")]
        cells.append(f"{r['ttd_p50_s_mean']:.1f}" if pd.notna(r["ttd_p50_s_mean"]) else "–")
        dz = f"{t.loc[m, 'cohens_dz']:.2f}" if m in t.index else "–"
        line = f"| {label[m]} | " + " | ".join(cells) + f" | {p_col} | {dz} |"
        return line.replace(r"$\pm$", "±").replace("--", "–")

    lines = [
        "# E1b tables (generated)",
        "",
        "Generated by `python -m fraudsim.experiments.scored_baselines report` from",
        "`results/e1_baselines/results.csv` and `results/e1b_scored_baselines/results.csv`",
        "with the paper's own helpers (`stats.summarize`, `stats.paired_vs`), so the numbers",
        f"match Table II. {len(keys)} paired runs per method (5 scenarios × seeds 1001-1010).",
        "Mean ± 95% t-interval over runs; a run without flags counts F1 = 0; TTD = mean over",
        "runs of the per-run median. p: paired Wilcoxon (zsplit) on run F1 against the proposed",
        "method, Holm-corrected over the 8 comparisons of the main table; d_z: Cohen's d_z.",
        "",
        "## Main table",
        "",
        "| Method | Precision | Recall | F1 | TTD (s) | p (Holm) | d_z |",
        "|---|---|---|---|---|---|---|",
        "| *Without scorer* | | | | | | |",
    ]
    for m in ["static_cap100", "static_cap10", "louvain", "plain_cc"]:
        lines.append(row(m, fmt_p(t.loc[m, "holm_p"])))
    lines.append("| *With the shipped calibrated scorer* | | | | | | |")
    for m in [f"{b}_scored" for b in ("static_cap100", "static_cap10", "louvain")]:
        lines.append(row(m, fmt_p(t.loc[m, "holm_p"])))
    lines.append(row("proposed", "–"))
    lines.append(row("proposed_default", fmt_p(t.loc["proposed_default", "holm_p"])))
    lines += [
        "",
        "## Scored baselines at the a-priori alert threshold 0.5 (uncorrected p)",
        "",
        "| Method | Precision | Recall | F1 | TTD (s) | p | d_z |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in secondary:
        lines.append(row(m, fmt_p(t.loc[m, "wilcoxon_p"])))
    lines += ["", "## Selected alert thresholds (validation seeds 301-303)", ""]
    sel_rec = json.loads(SELECTION.read_text(encoding="utf-8"))
    for b, a in sel.items():
        grid = ", ".join(f"{k}: {v:.3f}" for k, v in sel_rec["mean_f1_by_threshold"][b].items())
        lines.append(f"- {label[b]}: {a} (mean validation F1 by threshold: {grid})")
    e3 = E3B / "frontier_ci.json"
    if e3.exists():
        r = json.loads(e3.read_text(encoding="utf-8"))["best_f1"]
        lines += [
            "",
            "## E3b: frontier, best F1 with the scorer (shared-attribute rings)",
            "",
            f"- Hub-aware + scorer: {r['hub_scored']['f1']:.3f} ({r['hub_scored']['method']})",
            f"- Cap 10 + scorer: {r['cap_scored']['f1']:.3f} ({r['cap_scored']['method']})",
            f"- Difference {r['difference']:+.3f}, 95% bootstrap CI "
            f"[{r['difference_ci'][0]:+.3f}, {r['difference_ci'][1]:+.3f}] "
            f"(best re-selected per resample; hub better in "
            f"{r['share_of_resamples_hub_better']:.0%} of resamples)",
            "- Per-run paired Wilcoxon at the full-sample best thresholds: "
            f"{r['per_run_wilcoxon']}",
        ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_md}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["tune", "e1b", "e3b", "report"])
    args = ap.parse_args()
    {"tune": tune, "e1b": e1b, "e3b": e3b, "report": report}[args.step]()


if __name__ == "__main__":
    main()
