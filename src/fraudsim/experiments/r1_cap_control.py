"""
R1: degree cap inside the pairwise detector (docs/research/r1_protocol.md).

    python -m fraudsim.experiments.r1_cap_control tune --arms log,log_cap10
    python -m fraudsim.experiments.r1_cap_control select
    python -m fraudsim.experiments.r1_cap_control run --arms log,log_cap10
    python -m fraudsim.experiments.r1_cap_control report
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _merge, run_grid
from fraudsim.experiments.tuning import load_tuned

SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
VALIDATION_SEEDS = (301, 302, 303)
TEST_SEEDS = tuple(range(2001, 2011))
EDGE_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5)
ARMS = {
    "log": ("inverse_log_degree", None),
    "log_cap10": ("inverse_log_degree", 10),
    "const": ("none", None),
    "const_cap10": ("none", 10),
}
SELECTION = ROOT / "results/r1_tuning/selected.json"


def alert() -> float:
    tuned = load_tuned()
    assert tuned is not None
    return float(tuned["alert_threshold"])


def arm(name: str, edge: float, suffix: str = "") -> Method:
    weight, cap = ARMS[name]
    hub = {"weight_method": weight, "edge_threshold": edge}
    if cap is not None:
        hub["max_attr_degree"] = cap
    return Method(f"r1_{name}{suffix}", f"{name}, edge {edge}", _merge(PROPOSED, {"hub_aware": hub}),
                  family="r1", alert_threshold=alert())


def tune(arms: list[str]) -> None:
    for a in arms:
        run_grid(f"r1_tuning/{a}", SCENARIOS, VALIDATION_SEEDS,
                 [arm(a, e, f"_e{e}") for e in EDGE_GRID], ROOT / "results")


def select() -> dict:
    chosen, grid = {}, {}
    for a in ARMS:
        df = pd.read_csv(ROOT / f"results/r1_tuning/{a}/results.csv")
        s = {e: float(df[df["method"] == f"r1_{a}_e{e}"]["f1"].fillna(0).mean()) for e in EDGE_GRID}
        grid[a] = {str(e): round(v, 4) for e, v in s.items()}
        chosen[a] = max(EDGE_GRID, key=lambda e: (s[e], -e))
    out = {"edge_threshold": chosen, "on_grid_edge": {a: chosen[a] in (EDGE_GRID[0], EDGE_GRID[-1]) for a in chosen},
           "mean_f1_by_edge": grid, "alert_threshold": alert(),
           "selected_by": "max mean ring F1 on seeds 301-303 x 5 scenarios; ties to the lower value"}
    SELECTION.write_text(json.dumps(out, indent=2))
    print(json.dumps(out["edge_threshold"]), json.dumps(out["on_grid_edge"]))
    return out


def run(arms: list[str]) -> None:
    sel = json.loads(SELECTION.read_text())["edge_threshold"]
    methods = []
    for a in arms:
        if a == "static_cap10_scored":
            methods += [m for m in _scored_rules() if m.name == "static_cap10_scored"]
        else:
            methods.append(arm(a, float(sel[a])))
    run_grid(f"r1_cap_control/{'_'.join(arms)}", SCENARIOS, TEST_SEEDS, methods, ROOT / "results")


def _scored_rules() -> list[Method]:
    from fraudsim.experiments.scored_baselines import scored, selected

    return [scored("static_cap10", selected()["static_cap10"])]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["tune", "select", "run"])
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    arms = a.arms.split(",")
    {"tune": lambda: tune(arms), "select": select, "run": lambda: run(arms)}[a.step]()


if __name__ == "__main__":
    main()
