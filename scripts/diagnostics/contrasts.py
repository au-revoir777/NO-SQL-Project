"""
Paired contrasts for preregistered comparisons (R1, W3). Reads results CSVs only.

    python scripts/diagnostics/contrasts.py r1
    python scripts/diagnostics/contrasts.py w3
"""

from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
DELTA = 0.05


def load(pattern: str) -> pd.DataFrame:
    dfs = [pd.read_csv(p) for p in glob.glob(str(ROOT / pattern))]
    df = pd.concat(dfs, ignore_index=True)
    df["f1"] = df["f1"].fillna(0.0)
    return df


def pair(df: pd.DataFrame, a: str, b: str, col: str = "f1") -> pd.DataFrame:
    x = df[df.method == a].set_index(["scenario", "seed"])[col]
    y = df[df.method == b].set_index(["scenario", "seed"])[col]
    j = pd.concat([x.rename("a"), y.rename("b")], axis=1, join="inner").fillna(0.0)
    j["d"] = j.a - j.b
    return j.reset_index()


def contrast(df: pd.DataFrame, a: str, b: str, seed: int = 0) -> dict:
    j = pair(df, a, b)
    rng = np.random.default_rng(seed)
    d = j.d.to_numpy()
    n = len(d)
    groups = [g.d.to_numpy() for _, g in j.groupby("scenario")]
    w = np.array([len(g) for g in groups], float) / n
    boot = np.array([sum(wk * rng.choice(g, len(g)).mean() for wk, g in zip(w, groups))
                     for _ in range(10000)])
    flips = rng.choice([-1.0, 1.0], size=(20000, n))
    p_sf = float(((np.abs((flips * d).mean(1)) >= abs(d.mean()) - 1e-12).sum() + 1) / 20001)
    se = d.std(ddof=1) / math.sqrt(n)
    t95 = stats.t.ppf(0.95, n - 1)
    try:
        p_w = float(stats.wilcoxon(d, zero_method="zsplit").pvalue)
    except ValueError:
        p_w = 1.0
    per = {}
    for s, g in j.groupby("scenario"):
        x = g.d.to_numpy()
        h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / math.sqrt(len(x)) if len(x) > 1 else float("nan")
        per[s] = {"d": round(float(x.mean()), 3), "ci95": [round(float(x.mean() - h), 3), round(float(x.mean() + h), 3)],
                  "wtl": [int((x > 1e-9).sum()), int((abs(x) <= 1e-9).sum()), int((x < -1e-9).sum())]}
    ci90 = [float(d.mean() - t95 * se), float(d.mean() + t95 * se)]
    return {"a": a, "b": b, "n": n, "mean_a": round(float(j.a.mean()), 3), "mean_b": round(float(j.b.mean()), 3),
            "diff": round(float(d.mean()), 3),
            "ci95_cluster_boot": [round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
            "p_signflip": round(p_sf, 4), "p_wilcoxon_zsplit": round(p_w, 4),
            "ci90_t": [round(v, 3) for v in ci90], "equivalent_at_0.05": bool(-DELTA < ci90[0] and ci90[1] < DELTA),
            "wtl": [int((d > 1e-9).sum()), int((abs(d) <= 1e-9).sum()), int((d < -1e-9).sum())],
            "per_scenario": per}


def table(df: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    rows = []
    for m in methods:
        g = df[df.method == m]
        ev = {}
        for s in g["detected_by_evasion"].dropna():
            for k, (x, n) in json.loads(s).items():
                ev.setdefault(k, [0, 0])
                ev[k][0] += x
                ev[k][1] += n
        rows.append({"method": m, "n": len(g), "precision": round(g.precision.mean(), 3),
                     "recall": round(g.recall.mean(), 3), "f1": round(g.f1.mean(), 3),
                     "f1_ci95": round(1.96 * g.f1.std(ddof=1) / math.sqrt(len(g)), 3),
                     "ttd_p50": round(g.ttd_p50_s.median(), 1) if "ttd_p50_s" in g else None,
                     "detect_ms_p50": round(g.detect_ms_p50.median(), 1),
                     "hub_hiding": f"{ev.get('hub_hiding', [0, 0])[0]}/{ev.get('hub_hiding', [0, 0])[1]}",
                     "by_evasion": {k: f"{v[0]}/{v[1]}" for k, v in sorted(ev.items())}})
    return pd.DataFrame(rows)


def main() -> None:
    which = sys.argv[1]
    if which == "r1":
        df = load("results/r1_cap_control/*/results.csv")
        ms = ["r1_log", "r1_log_cap10", "r1_const", "r1_const_cap10", "static_cap10_scored"]
        print(table(df, ms).to_string(index=False))
        for a, b, role in [("r1_log", "r1_log_cap10", "PRIMARY H1"), ("r1_const", "r1_const_cap10", "secondary"),
                           ("r1_log", "r1_const", "secondary"), ("r1_log_cap10", "static_cap10_scored", "secondary")]:
            print(role, json.dumps(contrast(df, a, b)))
    elif which == "w3":
        df = load("results/w2_eval/*/results.csv")
        ms = list(dict.fromkeys(df.method))
        print(table(df, ms).to_string(index=False))
        for b in ms:
            if b != "proposed":
                print(json.dumps(contrast(df, "proposed", b)))


if __name__ == "__main__":
    main()
