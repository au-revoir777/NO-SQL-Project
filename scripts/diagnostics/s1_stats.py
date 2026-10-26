"""
S1 statistical audit (prompt 2). Reads existing results only; runs no experiment.

    python scripts/diagnostics/s1_stats.py > docs/paper/refine2/diag/s1_stats.txt
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "results"
RNG = np.random.default_rng(0)
DELTA = 0.05  # proposed equivalence margin (F1 points); to be confirmed by the authors


def load(exp: str) -> pd.DataFrame:
    df = pd.read_csv(R / exp / "results.csv")
    df["f1"] = df["f1"].fillna(0.0)
    return df


def paired(df_a: pd.DataFrame, a: str, df_b: pd.DataFrame, b: str, col: str = "f1",
           extra: list[str] | None = None) -> pd.DataFrame:
    keys = ["scenario", "seed"] + (extra or [])
    x = df_a[df_a["method"] == a].set_index(keys)[col]
    y = df_b[df_b["method"] == b].set_index(keys)[col]
    j = pd.concat([x.rename("a"), y.rename("b")], axis=1, join="inner").fillna(0.0)
    j["d"] = j["a"] - j["b"]
    return j.reset_index()


def strat_boot(j: pd.DataFrame, n: int = 10000) -> tuple[float, float]:
    groups = [g["d"].to_numpy() for _, g in j.groupby("scenario")]
    w = np.array([len(g) for g in groups], dtype=float)
    w /= w.sum()
    means = np.empty(n)
    for i in range(n):
        means[i] = sum(wk * RNG.choice(g, len(g)).mean() for wk, g in zip(w, groups))
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def strat_signflip(j: pd.DataFrame, n: int = 20000) -> float:
    """Sign-flip permutation test of the mean paired difference (flips within runs)."""
    d = j["d"].to_numpy()
    obs = abs(d.mean())
    flips = RNG.choice([-1.0, 1.0], size=(n, len(d)))
    return float(((np.abs((flips * d).mean(axis=1)) >= obs - 1e-12).sum() + 1) / (n + 1))


def summary(name: str, j: pd.DataFrame) -> dict:
    d = j["d"].to_numpy()
    n = len(d)
    sd = float(d.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n)
    t975, t95 = stats.t.ppf(0.975, n - 1), stats.t.ppf(0.95, n - 1)
    # minimum detectable paired difference, two-sided alpha 0.05, power 0.8 (t approx.)
    mde = (t975 + stats.t.ppf(0.8, n - 1)) * se
    # runs needed for TOST at margin DELTA, true diff 0, alpha 0.05, power 0.8
    n_tost = math.ceil(((stats.norm.ppf(0.95) + stats.norm.ppf(0.9)) * sd / DELTA) ** 2) if sd > 0 else 0
    try:
        p_w = float(stats.wilcoxon(d, zero_method="wilcox").pvalue) if np.any(d != 0) else 1.0
    except ValueError:
        p_w = float("nan")
    per = {s: round(float(g["d"].mean()), 3) for s, g in j.groupby("scenario")}
    out = {
        "comparison": name, "n": n, "mean_diff": round(float(d.mean()), 3), "sd_diff": round(sd, 3),
        "ci95_t": [round(float(d.mean() - t975 * se), 3), round(float(d.mean() + t975 * se), 3)],
        "ci90_t": [round(float(d.mean() - t95 * se), 3), round(float(d.mean() + t95 * se), 3)],
        "ci95_strat_boot": [round(v, 3) for v in strat_boot(j)],
        "wilcoxon_p": round(p_w, 4), "signflip_p": round(strat_signflip(j), 4),
        "win_tie_loss": [int((d > 1e-9).sum()), int((abs(d) <= 1e-9).sum()), int((d < -1e-9).sum())],
        "mde_80": round(float(mde), 3), "n_for_tost_delta": n_tost, "per_scenario_mean_diff": per,
    }
    # heterogeneity across scenarios: one-way ANOVA on paired differences
    groups = [g["d"].to_numpy() for _, g in j.groupby("scenario")]
    if len(groups) > 1 and all(len(g) > 1 for g in groups):
        out["scenario_heterogeneity_p"] = round(float(stats.f_oneway(*groups).pvalue), 4)
    return out


def newcombe(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float]:
    def wilson(x, n):
        z = 1.959964
        p = x / n
        c = (p + z * z / (2 * n)) / (1 + z * z / n)
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return c - h, c + h
    l1, u1 = wilson(x1, n1)
    l2, u2 = wilson(x2, n2)
    p1, p2 = x1 / n1, x2 / n2
    d = p1 - p2
    return d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def main() -> None:
    res = []
    e1, e1b = load("e1_baselines"), load("e1b_scored_baselines")
    res.append(summary("RQ1 proposed - cap10+scorer (Table II)", paired(e1, "proposed", e1b, "static_cap10_scored")))
    res.append(summary("RQ1 proposed - cap100+scorer", paired(e1, "proposed", e1b, "static_cap100_scored")))
    res.append(summary("RQ1 proposed - louvain+scorer", paired(e1, "proposed", e1b, "louvain_scored")))
    res.append(summary("RQ1 proposed - cap10 unscored", paired(e1, "proposed", e1, "static_cap10")))
    res.append(summary("RQ1 tuned - a-priori", paired(e1, "proposed", e1, "proposed_default")))
    e2 = load("e2_ablations")
    for v in ["no_hub_weight", "no_time_decay", "no_hysteresis", "no_scoring", "no_hub_aware", "no_cycle", "no_smurfing"]:
        res.append(summary(f"Table V full - {v}", paired(e2, "proposed", e2, v)))
    e2c, e2b = load("e2c_weight_functions"), load("e2b_hub_heavy")
    for w in ["w_none", "w_inverse_sqrt_degree", "w_inverse_degree_plain", "w_soft_cap"]:
        res.append(summary(f"E2c shipped - {w} (5 scen x 10)", paired(e2c, "w_inverse_log_degree", e2c, w)))
        res.append(summary(f"E2b shipped - {w} (hub_heavy x 30)", paired(e2b, "w_inverse_log_degree", e2b, w)))
    e4 = load("e4b_timer")
    for t in ["timer_1", "timer_5"]:
        res.append(summary(f"E4b inc - {t}", paired(e4, "inc", e4, t)))
    e13 = load("e13_learned_baselines")
    res.append(summary("RQ9 proposed - GB", paired(e13, "proposed", e13, "tabular_gb")))
    e5b = load("e5b_large_hubs")
    for size in (500, 2000):
        s = e5b[e5b["hub_size"] == size]
        res.append(summary(f"E5b log_fanout - log_full (hub {size})", paired(s, "log_fanout", s, "log_full")))
        res.append(summary(f"E5b const_fanout - const_full (hub {size})", paired(s, "const_fanout", s, "const_full")))
    for r in res:
        print(json.dumps(r))
    # small-n proportions
    print(json.dumps({"adaptive_on_minus_off": "18/22 - 9/11",
                      "diff": round(18 / 22 - 9 / 11, 3),
                      "newcombe95": [round(v, 3) for v in newcombe(18, 22, 9, 11)]}))
    for lbl, x, n in [("adaptive on", 18, 22), ("adaptive off", 9, 11), ("hub-hiding prop", 35, 52),
                      ("hub-hiding cap10", 33, 52), ("rotation prop", 4, 14), ("slow prop", 3, 13)]:
        ci = stats.binomtest(x, n).proportion_ci(method="exact")
        print(json.dumps({"proportion": lbl, "x": x, "n": n, "cp95": [round(ci.low, 3), round(ci.high, 3)]}))
    print(json.dumps({"hub_hiding_prop_minus_cap10_newcombe95": [round(v, 3) for v in newcombe(35, 52, 33, 52)]}))
    # 3-seed scale table: t-interval vs observed range
    e4s = pd.read_csv(R / "e4b_scale_hubs/results.csv")
    print("e4b_scale_hubs columns:", list(e4s.columns)[:12])


if __name__ == "__main__":
    main()
