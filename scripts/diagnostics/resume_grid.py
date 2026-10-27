"""Finish a run_grid experiment that was stopped part-way: run only the missing
(scenario, seed, method) rows. Streams are deterministic, so the rows equal an
uninterrupted run. Used for round3/amount_overlap (stopped by a time limit)."""
from __future__ import annotations

import pandas as pd

from fraudsim.experiments import round3 as r3
from fraudsim.experiments.harness import run_grid
from fraudsim.experiments.w2_baselines import GNN_MODEL


def main() -> None:
    a = [r3.pipe("pipe_all", model=f"{r3.SCORERS}/pipe_all.joblib"),
         r3.pipe("pipe_noamount", model=f"{r3.SCORERS}/pipe_noamount.joblib")]
    ms = a + [r3.gnn("gnn_unscored", GNN_MODEL), r3.rules_own()]
    done = pd.read_csv(r3.OUT / "round3/amount_overlap/results.csv")
    have = set(zip(done.scenario, done.seed, done.method, strict=True))
    for sc in r3.SCEN:
        for seed in range(3601, 3611):
            todo = [m for m in ms if (sc, seed, m.name) not in have]
            if todo:
                run_grid("round3/amount_overlap", [sc], [seed], todo, r3.OUT, scenario_overrides=r3.OVERLAP)


if __name__ == "__main__":
    main()
