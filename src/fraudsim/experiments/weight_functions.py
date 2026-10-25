"""
E2b (powered hub_heavy test of the hub weight) and E2c (weight functions across
scenarios), as fixed in docs/research/e2b_protocol.md.

    python -m fraudsim.experiments.weight_functions tune     # edge threshold per function
    python -m fraudsim.experiments.weight_functions e2b      # hub_heavy, seeds 1001-1030
    python -m fraudsim.experiments.weight_functions e2c      # 5 scenarios, seeds 1001-1010
    python -m fraudsim.experiments.weight_functions report   # docs/research/e2b_tables.md
"""

# ruff: noqa: RUF001  (tables use typographic dashes and signs)

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _merge, run_grid
from fraudsim.experiments.provenance import repo_relative
from fraudsim.experiments.scored_baselines import holm
from fraudsim.experiments.stats import fmt_ci, paired_vs, summarize
from fraudsim.experiments.tuning import load_tuned

ACCURACY_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
VALIDATION_SEEDS = (301, 302, 303)
E2B_SEEDS = tuple(range(1001, 1031))
E2C_SEEDS = tuple(range(1001, 1011))
EDGE_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)
SHIPPED = "inverse_log_degree"
FUNCTIONS = {
    "inverse_log_degree": "1/ln(1+d) (shipped)",
    "inverse_degree_plain": "1/d",
    "inverse_sqrt_degree": "1/sqrt(d)",
    "soft_cap": "soft cap at 10",
    "none": "constant",
}
SELECTION = ROOT / "results/e2b_hub_heavy/selected_edge_thresholds.json"


def alert() -> float:
    tuned = load_tuned()
    if tuned is None:
        raise RuntimeError("configs/tuned.json missing")
    return float(tuned["alert_threshold"])


def method(fn: str, edge: float, suffix: str = "") -> Method:
    return Method(
        f"w_{fn}{suffix}",
        f"{FUNCTIONS[fn]}{suffix and f', edge {edge}'}",
        _merge(PROPOSED, {"hub_aware": {"weight_method": fn, "edge_threshold": edge}}),
        family="weight_fn",
        alert_threshold=alert(),
    )


def tune(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> dict[str, float]:
    methods = [method(fn, e, f"_e{e}") for fn in FUNCTIONS for e in EDGE_GRID]
    path = run_grid("e2b_tuning", ACCURACY_SCENARIOS, VALIDATION_SEEDS, methods, Path(out), log=log)
    df = pd.read_csv(path)
    chosen: dict[str, float] = {}
    grid: dict[str, dict[str, float]] = {}
    for fn in FUNCTIONS:
        s = {e: float(df[df["method"] == f"w_{fn}_e{e}"]["f1"].fillna(0).mean()) for e in EDGE_GRID}
        grid[fn] = {str(e): round(v, 4) for e, v in s.items()}
        chosen[fn] = max(EDGE_GRID, key=lambda e: (s[e], -e))
        edge = " (on the grid edge)" if chosen[fn] in (EDGE_GRID[0], EDGE_GRID[-1]) else ""
        log(f"[e2b tune] {fn}: edge {chosen[fn]}{edge} (mean F1 {s[chosen[fn]]:.4f})")
    SELECTION.parent.mkdir(parents=True, exist_ok=True)
    SELECTION.write_text(
        json.dumps(
            {
                "edge_threshold": chosen,
                "mean_f1_by_edge": grid,
                "alert_threshold": alert(),
                "selected_by": "max mean ring F1 on validation seeds; ties to the lower value",
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
    raw = json.loads(SELECTION.read_text(encoding="utf-8"))["edge_threshold"]
    return {k: float(v) for k, v in raw.items()}


def _methods() -> list[Method]:
    sel = selected()
    return [method(fn, sel[fn]) for fn in FUNCTIONS]


def e2b(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    return run_grid("e2b_hub_heavy", ["hub_heavy"], E2B_SEEDS, _methods(), Path(out), log=log)


def e2c(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    return run_grid(
        "e2c_weight_functions", ACCURACY_SCENARIOS, E2C_SEEDS, _methods(), Path(out), log=log
    )


def _hub_hiding_recall(df: pd.DataFrame) -> float | None:
    det = tot = 0
    for v in df["detected_by_evasion"].dropna():
        hh = json.loads(v).get("hub_hiding")
        if hh:
            det, tot = det + hh[0], tot + hh[1]
    return det / tot if tot else None


def _table(df: pd.DataFrame, title: str, n_note: str) -> list[str]:
    s = summarize(df, ["method"]).set_index("method")
    t = paired_vs(df, f"w_{SHIPPED}", "f1").set_index("method")
    adj = holm({m: float(t.loc[m, "wilcoxon_p"]) for m in t.index})
    lines = [
        f"## {title}",
        "",
        n_note,
        "",
        "| h(d) | Edge thr. | Precision | Recall | F1 | Hub-hiding recall | p raw | p Holm | d_z |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    sel = selected()
    for fn, lab in FUNCTIONS.items():
        m = f"w_{fn}"
        r = s.loc[m]
        cells = [fmt_ci(r[f"{c}_mean"], r[f"{c}_ci95"]) for c in ("precision", "recall", "f1")]
        hh = _hub_hiding_recall(df[df["method"] == m])
        if m in t.index:
            p_raw, p_adj = float(t.loc[m, "wilcoxon_p"]), adj[m]
            stats = [_p(p_raw), _p(p_adj), f"{t.loc[m, 'cohens_dz']:.2f}"]
        else:
            stats = ["–", "–", "–"]
        row = [lab, f"{sel[fn]}", *cells, f"{hh:.2f}" if hh is not None else "–", *stats]
        lines.append(("| " + " | ".join(row) + " |").replace(r"$\pm$", "±").replace("--", "–"))
    lines.append("")
    lines.append("d_z and p: the shipped function minus the row's function, paired by run.")
    lines.append("")
    return lines


def _p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def report(out_md: Path = ROOT / "docs/research/e2b_tables.md") -> None:
    b = pd.read_csv(ROOT / "results/e2b_hub_heavy/results.csv")
    c = pd.read_csv(ROOT / "results/e2c_weight_functions/results.csv")
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))
    lines = [
        "# E2b / E2c tables (generated)",
        "",
        "Generated by `python -m fraudsim.experiments.weight_functions report` with the paper's",
        "helpers (`stats.summarize`, `stats.paired_vs`, zsplit Wilcoxon). Mean ± 95% t-interval",
        f"over runs. Alert threshold {sel['alert_threshold']} for every function.",
        "",
    ]
    lines += _table(b, "E2b: hub_heavy, seeds 1001-1030", f"{b['seed'].nunique()} paired runs.")
    lines += _table(
        c,
        "E2c: 5 scenarios, seeds 1001-1010",
        f"{c['seed'].nunique() * c['scenario'].nunique()} paired runs per function.",
    )
    per = c.pivot_table(index="method", columns="scenario", values="f1", aggfunc="mean")
    lines += ["### E2c F1 by scenario", "", "| h(d) | " + " | ".join(per.columns) + " |"]
    lines.append("|---" * (len(per.columns) + 1) + "|")
    for fn, lab in FUNCTIONS.items():
        lines.append(f"| {lab} | " + " | ".join(f"{v:.2f}" for v in per.loc[f"w_{fn}"]) + " |")
    lines += ["", "## Edge thresholds selected on validation seeds 301-303", ""]
    for fn, lab in FUNCTIONS.items():
        g = ", ".join(f"{k}: {v:.3f}" for k, v in sel["mean_f1_by_edge"][fn].items())
        lines.append(f"- {lab}: {sel['edge_threshold'][fn]} ({g})")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_md}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["tune", "e2b", "e2c", "report"])
    args = ap.parse_args()
    {"tune": tune, "e2b": e2b, "e2c": e2c, "report": report}[args.step]()


if __name__ == "__main__":
    main()
