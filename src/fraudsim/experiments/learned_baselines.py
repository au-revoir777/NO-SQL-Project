"""
E13 (learned tabular baseline) and E14 (evasion-strength sweeps), as fixed in
docs/research/e13_e14_protocol.md.

    python -m fraudsim.experiments.learned_baselines train      # GB on plain_cc candidates
    python -m fraudsim.experiments.learned_baselines tune       # alert threshold, seeds 301-303
    python -m fraudsim.experiments.learned_baselines e13        # E1 protocol, seeds 1001-1010
    python -m fraudsim.experiments.learned_baselines e14        # evasion-strength sweeps
    python -m fraudsim.experiments.learned_baselines report     # docs/research/e13/e14 tables
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.harness import (
    ROOT,
    Method,
    baseline_methods,
    make_stream,
    run_grid,
)
from fraudsim.experiments.provenance import recorded, repo_relative
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage
from fraudsim.scoring.train import Row, _matrix, write_rows
from fraudsim.types import config_hash

TRAIN_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift", "scale_sweep")
ACCURACY_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
TRAIN_SEEDS = tuple(range(101, 111))
VALIDATION_SEEDS = (301, 302, 303)
TEST_SEEDS = tuple(range(1001, 1011))
ALERT_GRID = (0.2, 0.3, 0.5, 0.7, 0.8, 0.9)
FIT_FRACTION = 0.7
DASH = chr(0x2013)  # en dash for empty table cells
MODEL_REL = "results/e13_learned_baselines/tabular_gb_scorer.joblib"
SELECTION = ROOT / "results/e13_learned_baselines/selected_threshold.json"
SWEEPS: dict[str, tuple[str, list[Any]]] = {
    "decoy_edges": ("decoys_per_action", [0, 1, 2, 4, 8]),
    "low_and_slow": ("rate_multiplier", [1, 2, 4, 8, 16]),
    "identity_rotation": ("rotate_every", [0, 12, 6, 3, 1]),
}


def plain_cc_overrides() -> dict[str, dict[str, Any]]:
    """E1's connected-components grouping (degenerate here: see protocol amendment 1)."""
    return next(m for m in baseline_methods() if m.name == "plain_cc").overrides


def candidate_overrides() -> dict[str, dict[str, Any]]:
    """
    tabular_gb's candidate groups (protocol amendment 1): E1's Louvain grouping
    with the density filter off, so the learned model decides, not a density rule.
    """
    base = next(m for m in baseline_methods() if m.name == "louvain").overrides
    out = {k: dict(v) for k, v in base.items()}
    out["community"] = {**out.get("community", {}), "min_density": 0.0}
    return out


def tabular_gb(threshold: float) -> Method:
    return Method(
        "tabular_gb",
        "Gradient boosting on candidate groups (no rule stage)",
        candidate_overrides(),
        scored=True,
        family="learned_baseline",
        alert_threshold=threshold,
        model_path=MODEL_REL,
    )


# ─── Training (the shipped scorer's protocol, on plain_cc candidates) ─────────


def collect_candidate_rows(scenario: str, seed: int) -> tuple[list[Row], dict[str, Any]]:
    stream = make_stream(scenario, seed)
    store = InMemoryGraphStore()
    stage = ScoringStage(scorer=None, record=True)
    engine = DetectionEngine(
        store,
        build_detectors(store, candidate_overrides()),
        tracker=RingTracker(EnsembleConfig()),
        config=EngineConfig(batch_size=50, full_interval_s=5.0),
        scorer=stage,
    )
    engine.run(stream.events)
    gen = stream.generator
    start = gen.ts(0.0).timestamp()
    duration = gen.ts().timestamp() - start
    truth = [
        {u for _, action, u in ring.member_history if action == "join"}
        for ring in gen.ledger.rings.values()
    ]
    rows = []
    for r in stage.rows:
        best = max((jaccard(set(r["members"]), gt) for gt in truth), default=0.0)
        rows.append(
            Row(
                scenario=scenario,
                seed=seed,
                run_id=f"e13_train:{scenario}:{seed}",
                ring_id=r["ring_id"],
                t_frac=(r["t"] - start) / duration if duration else 0.0,
                status=r["status"],
                label=int(best >= 0.5),
                best_jaccard=round(best, 4),
                features=r["features"],
            )
        )
    info = {
        "scenario": scenario,
        "seed": seed,
        "config_hash": config_hash(stream.raw),
        "stream_digest": gen.digest[:16],
        "rows": len(rows),
        "positives": sum(r.label for r in rows),
    }
    return rows, info


def train(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    out_dir = Path(out) / "e13_learned_baselines"
    model = ROOT / MODEL_REL
    details = {
        "protocol": "docs/research/e13_e14_protocol.md",
        "step": "train",
        "scenarios": list(TRAIN_SCENARIOS),
        "train_seeds": list(TRAIN_SEEDS),
        "fit_fraction": FIT_FRACTION,
        "candidates": candidate_overrides(),
    }
    with recorded(out_dir, "e13_train", details) as entry:
        rows: list[Row] = []
        runs = []
        for sc in TRAIN_SCENARIOS:
            for seed in TRAIN_SEEDS:
                r, info = collect_candidate_rows(sc, seed)
                rows += r
                runs.append(info)
                log(f"[e13 train] {sc} seed={seed}: {info['rows']} rows, {info['positives']} pos")
        fit = [r for r in rows if r.t_frac < FIT_FRACTION]
        cal = [r for r in rows if r.t_frac >= FIT_FRACTION]
        scorer = RingScorer("gradient_boosting").fit(*_matrix(fit), *_matrix(cal))
        scorer.meta.train = {
            "protocol": "docs/research/e13_e14_protocol.md",
            "candidates": "louvain, min_density 0 (amendment 1)",
            "scenarios": list(TRAIN_SCENARIOS),
            "train_seeds": list(TRAIN_SEEDS),
            "fit_fraction": FIT_FRACTION,
            "rows": {"fit": len(fit), "calibration": len(cal)},
            "runs": runs,
        }
        scorer.meta.metrics = {"calibration_slice": scorer.evaluate(*_matrix(cal))}
        scorer.save(model)
        write_rows(out_dir / "training_rows.csv", rows)
        entry["model"] = {"path": MODEL_REL, "rows": len(rows)}
    return model


# ─── Threshold selection (validation seeds only) ──────────────────────────────


def tune(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> float:
    methods = [
        Method(
            f"tabular_gb_a{a}",
            f"tabular_gb alert {a}",
            candidate_overrides(),
            family="tuning",
            alert_threshold=a,
            model_path=MODEL_REL,
        )
        for a in ALERT_GRID
    ]
    path = run_grid("e13_tuning", ACCURACY_SCENARIOS, VALIDATION_SEEDS, methods, Path(out), log=log)
    df = pd.read_csv(path)
    scores = {
        a: float(df[df["method"] == f"tabular_gb_a{a}"]["f1"].fillna(0).mean()) for a in ALERT_GRID
    }
    best = max(ALERT_GRID, key=lambda a: (scores[a], -a))
    SELECTION.write_text(
        json.dumps(
            {
                "alert_threshold": best,
                "mean_f1_by_threshold": scores,
                "validation_seeds": list(VALIDATION_SEEDS),
                "scenarios": list(ACCURACY_SCENARIOS),
                "results": repo_relative(path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"[e13 tune] selected alert threshold {best} (mean F1 {scores[best]:.4f})")
    return best


def selected_threshold() -> float:
    return float(json.loads(SELECTION.read_text(encoding="utf-8"))["alert_threshold"])


# ─── E13 and E14 ──────────────────────────────────────────────────────


def e13(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    from fraudsim.experiments.suite import tuned_proposed

    return run_grid(
        "e13_learned_baselines",
        ACCURACY_SCENARIOS,
        TEST_SEEDS,
        [tuned_proposed(), tabular_gb(selected_threshold())],
        Path(out),
        log=log,
    )


def sweep_overrides(mode: str, value: Any) -> dict[str, Any]:
    knob, _ = SWEEPS[mode]
    if mode == "low_and_slow":
        params = {"action_mult": float(value), "grow_mult": float(value)}
    else:
        params = {knob: int(value)}
    return {
        "random_rings.evasion_weights": {mode: 1.0},
        "simulation.evasion_params": {mode: params},
    }


def e14(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    from fraudsim.experiments.suite import tuned_proposed

    methods = [
        tuned_proposed(),
        *[m for m in baseline_methods() if m.name in ("static_cap10", "louvain")],
    ]
    methods.append(tabular_gb(selected_threshold()))
    path = Path(out) / "e14_evasion_strength" / "results.csv"
    for mode, (knob, values) in SWEEPS.items():
        for value in values:
            run_grid(
                "e14_evasion_strength",
                ["high_noise"],
                TEST_SEEDS,
                methods,
                Path(out),
                scenario_overrides=sweep_overrides(mode, value),
                log=log,
                extra_columns={"sweep_mode": mode, "sweep_knob": knob, "sweep_value": value},
            )
    return path


# ─── Report ───────────────────────────────────────────────────────────


def paired(a: Sequence[float], b: Sequence[float]) -> dict[str, Any]:
    """Two-sided Wilcoxon signed-rank on paired values, median difference (a - b),
    and the matched-pairs rank-biserial correlation."""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    nz = d[d != 0]
    if len(nz) == 0:
        return {"n": len(d), "median_diff": 0.0, "p": None, "rank_biserial": 0.0}
    ranks = pd.Series(np.abs(nz)).rank().to_numpy()
    rb = (ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum()
    p = float(wilcoxon(nz).pvalue) if len(nz) >= 1 else None
    return {
        "n": len(d),
        "median_diff": round(float(np.median(d)), 4),
        "p": ("<0.001" if p < 0.001 else round(p, 4)) if p is not None else None,
        "rank_biserial": round(float(rb), 3),
    }


def _swept_recall(row: pd.Series, mode: str) -> float | None:
    by = json.loads(row["recall_by_evasion"]) if isinstance(row["recall_by_evasion"], str) else {}
    return by.get(mode)


def report(out_md: Path = ROOT / "docs/research/e13_tables.md") -> None:
    e13 = pd.read_csv(ROOT / "results/e13_learned_baselines/results.csv")
    e1 = pd.read_csv(ROOT / "results/e1_baselines/results.csv")
    sel = json.loads(SELECTION.read_text(encoding="utf-8"))
    lines = [
        "# E13 tables (generated)",
        "",
        "Generated by `python -m fraudsim.experiments.learned_baselines report` from "
        "`results/e13_learned_baselines/`. Do not edit by hand. Means over seeds 1001-1010; "
        "Wilcoxon on paired ring-level F1 (tabular_gb - proposed).",
        "",
        f"Selected alert threshold (validation seeds 301-303): **{sel['alert_threshold']}** "
        f"(mean F1 by threshold: "
        + ", ".join(f"{k}: {v:.3f}" for k, v in sel["mean_f1_by_threshold"].items())
        + ").",
        "",
    ]
    digests = e13.merge(
        e1[e1["method"] == "proposed"][["scenario", "seed", "stream_digest"]],
        on=["scenario", "seed"],
        suffixes=("", "_e1"),
    )
    same_digest = int((digests["stream_digest"] == digests["stream_digest_e1"]).sum())
    lines.append(f"Stream digests equal to E1's: {same_digest} of {len(digests)} rows.")
    lines += [
        "",
        "| Scenario | Method | Precision | Recall | F1 | User F1 | Node AUC* | Alerts/h | "
        "ΔF1 median (GB - proposed) | p | Rank-biserial |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sc in [*ACCURACY_SCENARIOS, "all"]:
        g = e13 if sc == "all" else e13[e13["scenario"] == sc]
        prop = g[g["method"] == "proposed"].sort_values(["scenario", "seed"])
        gb = g[g["method"] == "tabular_gb"].sort_values(["scenario", "seed"])
        stat = paired(gb["f1"].fillna(0), prop["f1"].fillna(0))
        for name, h in (("proposed", prop), ("tabular_gb", gb)):
            cells = " | ".join(
                f"{h[c].mean():.3f}" if h[c].notna().any() else DASH
                for c in ("precision", "recall", "f1", "user_f1", "node_auc", "alerts_per_hour")
            )
            extra = (
                f" | {stat['median_diff']:+.3f} | {stat['p'] if stat['p'] is not None else DASH} | "
                f"{stat['rank_biserial']:+.3f}"
                if name == "tabular_gb"
                else " | | |"
            )
            lines.append(f"| {sc} | {name} | {cells}{extra} |")
    lines += [
        "",
        "*Node-level AUC over every account of the stream; not comparable to YelpChi, "
        "Amazon or Elliptic numbers in the literature (different data, unit and labels).",
    ]
    Path(out_md).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    p14 = ROOT / "results/e14_evasion_strength/results.csv"
    if not p14.exists():
        return
    e14 = pd.read_csv(p14)
    e14["swept_recall"] = [_swept_recall(r, r["sweep_mode"]) for _, r in e14.iterrows()]
    out14 = [
        "# E14 tables (generated)",
        "",
        "Generated by `python -m fraudsim.experiments.learned_baselines report` from "
        "`results/e14_evasion_strength/`. Do not edit by hand. high_noise with every random "
        "ring using the swept mode; means over seeds 1001-1010 with bootstrap 95% CI "
        "(2,000 resamples, seed 0); Wilcoxon on paired swept-mode recall vs proposed.",
        "",
    ]
    rng = np.random.default_rng(0)

    def ci(xs: np.ndarray) -> str:
        xs = xs[~np.isnan(xs)]
        if len(xs) == 0:
            return DASH
        boots = [rng.choice(xs, len(xs)).mean() for _ in range(2000)]
        return (
            f"{xs.mean():.2f} [{np.percentile(boots, 2.5):.2f}, {np.percentile(boots, 97.5):.2f}]"
        )

    for mode, (knob, values) in SWEEPS.items():
        out14 += [
            f"## {mode} ({knob})",
            "",
            "| Value | Method | Swept-mode recall | Precision | F1 | Node AUC* | "
            "Δrecall vs proposed (median) | p |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
        g = e14[e14["sweep_mode"] == mode]
        for v in values:
            gv = g[g["sweep_value"] == v]
            prop = gv[gv["method"] == "proposed"].sort_values("seed")
            for m in ("proposed", "static_cap10", "louvain", "tabular_gb"):
                h = gv[gv["method"] == m].sort_values("seed")
                if h.empty:
                    continue
                stat = (
                    paired(h["swept_recall"].fillna(0), prop["swept_recall"].fillna(0))
                    if m != "proposed"
                    else None
                )
                arr = {c: h[c].to_numpy(dtype=float) for c in ("swept_recall", "precision", "f1")}

                if stat:
                    pval = stat["p"] if stat["p"] is not None else DASH
                    vs = f"{stat['median_diff']:+.2f} | {pval}"
                else:
                    vs = " | "
                out14.append(
                    f"| {v} | {m} | {ci(arr['swept_recall'])} | {ci(arr['precision'])} | "
                    f"{ci(arr['f1'])} | {h['node_auc'].mean():.3f} | {vs} |"
                )
        out14.append("")
    out14 += ["*Not comparable to YelpChi, Amazon or Elliptic numbers in the literature."]
    (Path(out_md).parent / "e14_tables.md").write_text(
        "\n".join(out14) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("step", choices=["train", "tune", "e13", "e14", "report"])
    args = p.parse_args()
    t0 = time.perf_counter()
    {"train": train, "tune": tune, "e13": e13, "e14": e14, "report": report}[args.step]()
    print(f"[{args.step}] done in {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
