"""
Result figures for the GNN extension and AnchorPipe (round 3), computed from committed results.

  docs/paper/figures/fig7_anchor.{pdf,png}     (a) F1 by test block, (b) the guard statistic over time
  docs/paper/figures/fig8_contrasts.{pdf,png}  forest plot of the paired differences behind the claims

The guard traces need GNN scores, so they are computed once (GraphSAGE only, no
detectors) and cached in results/anchor/guard_traces.csv; delete that file to recompute.

    python scripts/make_anchor_figures.py
"""

# ruff: noqa: RUF001

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "diagnostics"))
import contrasts as c  # noqa: E402

from fraudsim.experiments import plotting  # noqa: E402,F401  (paper rcParams)

OUT = ROOT / "docs" / "paper" / "figures"
# Categorical slots in fixed order (reference palette, validated: scripts in the dataviz skill).
SERIES = {
    "anchor": ("AnchorPipe", "#2a78d6"),
    "gnn_unscored": ("GraphSAGE", "#eb6834"),
    "sagepipe": ("SagePipe (no guard)", "#1baf7a"),
    "hybrid": ("Hybrid", "#eda100"),
    "proposed": ("Pipeline (shipped)", "#e87ba4"),
    "rules": ("Rules + scorer", "#008300"),
}
INK, MUTED, GRID = "#1f2328", "#6b6a66", "#d9d8d4"
BLOCKS = [("T1", "In distribution\n(5101–5120)"), ("T2", "Amounts overlap\n(5201–5210)"),
          ("T3", "Stronger shift\n(5301–5310)")]


def _ci(x: np.ndarray) -> float:
    from scipy import stats

    return float(stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else 0.0


def guard_traces() -> pd.DataFrame:
    path = ROOT / "results" / "anchor" / "guard_traces.csv"
    if path.exists():
        return pd.read_csv(path)
    from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
    from fraudsim.experiments.anchor import _gnn, guard_stat
    from fraudsim.experiments.harness import make_stream
    from fraudsim.experiments.w2_baselines import GNN_MODEL
    from fraudsim.graph.store import InMemoryGraphStore

    off = {k: {"enabled": False} for k in ("static_cypher", "hub_aware", "temporal_cycle", "smurfing", "community")}
    rows = []
    for label, seed, ov in (("in distribution", 5101, {}),
                            ("amounts overlap (median 2,000)", 5201, {"simulation.amount_median": 2000}),
                            ("stronger shift (median 5,000)", 5301, {"simulation.amount_median": 5000})):
        stream = make_stream("hub_heavy", seed, ov)
        store = InMemoryGraphStore()
        eng = DetectionEngine(store, build_detectors(store, {**off, "gnn": {
            "model_path": GNN_MODEL, "node_threshold": 0.95, "as_full_detector": True}}),
            config=EngineConfig(batch_size=50, full_interval_s=0.0))
        det = _gnn(eng)
        start = stream.generator.ts(0.0).timestamp()
        for batch in eng.batches(stream.events):
            eng.process(batch)
            g = guard_stat(det)
            if g is not None:
                rows.append({"stream": label, "seed": seed, "t": batch[-1].ts.timestamp() - start, "g": g})
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def fig7() -> None:
    import json

    tau = json.loads((ROOT / "results/anchor/guard_reference.json").read_text())["tau"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.16, 2.5), gridspec_kw={"width_ratios": [1.5, 1]})
    n = len(SERIES)
    width = 0.8 / n
    for bi, (b, _) in enumerate(BLOCKS):
        df = c.load(f"results/anchor_{b}/*/results.csv")
        for si, (m, (_, col)) in enumerate(SERIES.items()):
            x = df[df.method == m].f1.to_numpy()
            pos = bi + (si - (n - 1) / 2) * width
            ax.bar(pos, x.mean(), width * 0.86, color=col, edgecolor="white", linewidth=0.6)
            ax.errorbar(pos, x.mean(), yerr=_ci(x), color=INK, lw=0.7, capsize=1.5, capthick=0.7)
            if m == "gnn_unscored" and x.mean() < 0.03:  # a zero bar must not read as missing
                ax.text(pos, 0.015, "0", ha="center", va="bottom", fontsize=6.5, color=INK)
            if m == "anchor":
                ax.text(pos, x.mean() + _ci(x) + 0.03, f"{x.mean():.2f}", ha="center", va="bottom",
                        fontsize=6.5, color=INK)
    ax.set_xticks(range(len(BLOCKS)), [t for _, t in BLOCKS])
    ax.set_ylim(0, 1.18)
    ax.set_yticks(np.arange(0, 1.01, 0.2))
    ax.set_ylabel("Ring F1 (mean, 95% CI)")
    ax.yaxis.grid(True, color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0)
    ax.set_title("(a) F1 on fresh test blocks", loc="left", fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, color=col) for _, col in SERIES.values()]
    ax.legend(handles, [lab for lab, _ in SERIES.values()], ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, 1.02), handlelength=1.0, columnspacing=0.8, fontsize=6.5)

    tr = guard_traces()
    styles = {"in distribution": ("#2a78d6", "-"), "amounts overlap (median 2,000)": ("#eb6834", "-"),
              "stronger shift (median 5,000)": ("#b0402a", "--")}
    for name, g in tr.groupby("stream", sort=False):
        col, ls = styles[name]
        bx.plot(g.t, g.g, color=col, ls=ls, lw=1.4, label=name)
    bx.axhline(tau, color=INK, lw=0.8, ls=":")
    bx.text(tr.t.max(), tau - 0.03, f"guard threshold τ = {tau:.3f}", ha="right", va="top", fontsize=6.5,
            color=INK)
    bx.set_ylim(0, 1.05)
    bx.set_xlabel("simulated time (s), hub_heavy stream")
    bx.set_ylabel("Share of users flagged")
    bx.yaxis.grid(True, color=GRID, lw=0.5)
    bx.set_axisbelow(True)
    bx.legend(loc="upper right", bbox_to_anchor=(1.0, 0.86), fontsize=6.5, handlelength=1.6)
    bx.set_title("(b) Label-free shift guard", loc="left", fontweight="bold")
    fig.tight_layout(w_pad=1.5)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig7_anchor.{ext}")
    plt.close(fig)


def fig8() -> None:
    """Forest plot: every paired difference the paper's claims rest on (filled = confirmatory)."""
    rows = [
        ("Hub links", None, None, None, None),
        ("Keep links − cap 10 (2001–2010)", "results/r1_cap_control/*/results.csv", "r1_log", "r1_log_cap10", True),
        ("Keep links − cap 27 (3001–3020)", "results/round3/capsweep/results.csv", "keep_links", "cap27", False),
        ("Step weight − 1/ln(1+d) (3101–3120)", "results/round3/step/results.csv", "step27", "log_shipped", False),
        ("GNN in the pipeline", None, None, None, None),
        ("EvidPipe − GraphSAGE (4001–4020)", "results/evidgnn_main/*/results.csv", "evidpipe", "gnn_unscored", True),
        ("EvidPipe − GraphSAGE (4101–4120)", "results/evidgnn_ablation/*/results.csv", "evidpipe", "gnn_unscored",
         False),
        ("SagePipe − GraphSAGE (4801–4820)", "results/evidgnn_follow/*/results.csv", "sagepipe", "gnn_unscored",
         False),
        ("Gate on − gate off (4101–4120)", "results/evidgnn_ablation/*/results.csv", "evidgnn", "evidgnn_nogate",
         True),
        ("GNN-aware − shipped scorer (4101–4120)", "results/evidgnn_ablation/*/results.csv", "evidpipe",
         "evidpipe_shipped_scorer", False),
        ("AnchorPipe (shift guard)", None, None, None, None),
        ("AnchorPipe − GraphSAGE, in distribution", "results/anchor_T1/*/results.csv", "anchor", "gnn_unscored",
         True),
        ("AnchorPipe − SagePipe, amounts overlap", "results/anchor_T2/*/results.csv", "anchor", "sagepipe", True),
        ("AnchorPipe − pipeline, amounts overlap", "results/anchor_T2/*/results.csv", "anchor", "proposed", True),
        ("AnchorPipe − rules, stronger shift", "results/anchor_T3/*/results.csv", "anchor", "rules", False),
        ("AnchorPipe − guard only, in distribution", "results/anchor_T1/*/results.csv", "anchor", "guard_only", False),
    ]
    fig, ax = plt.subplots(figsize=(3.5, 4.3))
    y = 0
    ticks, labels = [], []
    for lab, pat, a, b, conf in rows:
        if pat is None:
            ticks.append(y)
            labels.append(lab)
            y -= 1
            continue
        k = c.contrast(c.load(pat), a, b)
        lo, hi = k["ci95_cluster_boot"]
        ax.plot([lo, hi], [y, y], color=INK, lw=1.0)
        ax.plot(k["diff"], y, "o", ms=4.2, mfc=INK if conf else "white", mec=INK, mew=1.0)
        ticks.append(y)
        labels.append(lab)
        y -= 1
    ax.axvspan(-0.05, 0.05, color="#efeeea", zorder=0)
    ax.axvline(0, color=MUTED, lw=0.7)
    ax.set_yticks(ticks, labels, fontsize=6.5)
    for t, lab in zip(ax.get_yticklabels(), labels, strict=True):
        if lab in ("Hub links", "GNN in the pipeline", "AnchorPipe (shift guard)"):
            t.set_fontweight("bold")
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Paired difference in ring F1 (95% CI)\nshaded: ±0.05 equivalence band")
    ax.set_ylim(y + 0.4, 0.6)
    ax.spines["left"].set_visible(False)
    ax.set_xticks([-0.1, 0.0, 0.1, 0.2])
    ax.plot([], [], "o", mfc=INK, mec=INK, ms=4, label="confirmatory")
    ax.plot([], [], "o", mfc="white", mec=INK, ms=4, label="exploratory")
    ax.legend(loc="upper right", fontsize=6.5, handletextpad=0.3, bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"fig8_contrasts.{ext}")
    plt.close(fig)


if __name__ == "__main__":
    fig7()
    fig8()
    print("wrote fig7_anchor and fig8_contrasts")
