"""
E2d: separate alert thresholds for hub-aware and transaction-only rings
(docs/research/e2d_protocol.md).

    python -m fraudsim.experiments.detector_thresholds tune   # validation seeds 301-303
    python -m fraudsim.experiments.detector_thresholds test   # seeds 1001-1010
    python -m fraudsim.experiments.detector_thresholds report
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from fraudsim.experiments.harness import ROOT, Method, run_grid
from fraudsim.experiments.stats import paired_vs, summarize
from fraudsim.experiments.suite import tuned_proposed

ACCURACY_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
VALIDATION_SEEDS = (301, 302, 303)
TEST_SEEDS = tuple(range(1001, 1011))
GRID = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
SHIPPED = (0.8, 0.8)
SELECTION = ROOT / "results/e2d_detector_thresholds/selected.json"


def method(a_hub: float, a_other: float, name: str | None = None) -> Method:
    m = tuned_proposed(name or f"det_h{a_hub}_o{a_other}", f"hub {a_hub}, other {a_other}")
    m.detector_thresholds = {"hub_aware": a_hub, "other": a_other}
    m.family = "detector_thresholds"
    return m


def tune(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> tuple[float, float]:
    methods = [method(h, o) for h in GRID for o in GRID]
    path = run_grid("e2d_tuning", ACCURACY_SCENARIOS, VALIDATION_SEEDS, methods, Path(out), log=log)
    df = pd.read_csv(path)
    scores = {
        (h, o): float(df[df["method"] == f"det_h{h}_o{o}"]["f1"].fillna(0).mean())
        for h in GRID
        for o in GRID
    }
    best = max(
        scores,
        key=lambda k: (round(scores[k], 6), -abs(k[0] - SHIPPED[0]) - abs(k[1] - SHIPPED[1])),
    )
    SELECTION.parent.mkdir(parents=True, exist_ok=True)
    SELECTION.write_text(
        json.dumps(
            {
                "a_hub": best[0],
                "a_other": best[1],
                "mean_f1": round(scores[best], 4),
                "shipped_mean_f1": round(scores[SHIPPED], 4),
                "grid": {f"{h},{o}": round(v, 4) for (h, o), v in scores.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"[e2d tune] selected hub {best[0]}, other {best[1]} (F1 {scores[best]:.4f})")
    return best


def test(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))
    m = method(sel["a_hub"], sel["a_other"], "det_selected")
    return run_grid(
        "e2d_detector_thresholds", ACCURACY_SCENARIOS, TEST_SEEDS, [m], Path(out), log=log
    )


def report(out_md: Path = ROOT / "docs/research/e2d_tables.md") -> None:
    e1 = pd.read_csv(ROOT / "results/e1_baselines/results.csv")
    e2d = pd.read_csv(ROOT / "results/e2d_detector_thresholds/results.csv")
    df = pd.concat([e1[e1["method"] == "proposed"], e2d], ignore_index=True)
    s = summarize(df, ["method"]).set_index("method")
    t = paired_vs(df, "proposed", "f1").set_index("method")
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))
    lines = [
        "# E2d tables (generated)",
        "",
        f"Selected on validation seeds: hub {sel['a_hub']}, other {sel['a_other']} "
        f"(mean validation F1 {sel['mean_f1']}; shipped 0.8/0.8: {sel['shipped_mean_f1']}).",
        "",
        "| Policy | Precision | Recall | F1 | p vs shipped | d_z |",
        "|---|---|---|---|---|---|",
    ]
    for m, lab in (
        ("proposed", "single threshold 0.8 (shipped)"),
        ("det_selected", "per detector"),
    ):
        r = s.loc[m]
        p = f"{t.loc[m, 'wilcoxon_p']:.3f}" if m in t.index else "-"
        dz = f"{t.loc[m, 'cohens_dz']:.2f}" if m in t.index else "-"
        lines.append(
            f"| {lab} | {r['precision_mean']:.2f} | {r['recall_mean']:.2f} | {r['f1_mean']:.2f}"
            f" | {p} | {dz} |"
        )
    lines.append("")
    lines.append("d_z: shipped minus per-detector, paired by run.")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_md}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["tune", "test", "report"])
    {"tune": tune, "test": test, "report": report}[ap.parse_args().step]()


if __name__ == "__main__":
    main()
