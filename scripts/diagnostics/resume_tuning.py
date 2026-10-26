"""
Resume a W2 tuning grid in parallel shards without repeating recorded runs.
Same methods, seeds and scenarios as `w2_baselines.tune`; only the scheduling differs.

    python scripts/diagnostics/resume_tuning.py gnn 0 2   # shard 0 of 2
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from fraudsim.experiments import w2_baselines as w
from fraudsim.experiments.harness import _append, make_stream, run_method
from fraudsim.scoring.scorer import RingScorer


def main() -> None:
    method, shard, n_shards = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    name, grid, _ = w.STRUCT[method]
    ms = [w.make(method, v, a) for v in grid for a in w.ALERT_GRID]
    if method == "gnn":
        ms += [w.make(method, v, None, scored=False) for v in grid]
    base = w.OUT / f"w2_tuning/{method}"
    done = set()
    for p in base.glob("results*.csv"):
        df = pd.read_csv(p)
        done |= {(r.scenario, int(r.seed), r.method) for r in df.itertuples()}
    todo = [(sc, seed, m) for sc in w.SCENARIOS for seed in w.VALIDATION_SEEDS for m in ms
            if (sc, seed, m.name) not in done]
    mine = todo[shard::n_shards]
    print(f"{len(done)} done, {len(todo)} to do, shard {shard}: {len(mine)}", flush=True)
    scorer = RingScorer.load(w.ROOT / f"{w.SCORERS}/{method}.joblib")
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"results_shard{shard}.csv"
    streams: dict = {}
    for sc, seed, m in mine:
        key = (sc, seed)
        if key not in streams:
            streams.clear()
            streams[key] = make_stream(sc, seed)
        row = run_method(streams[key], m, scorer if m.scored else None, f"w2_tuning/{method}")
        _append(out, row)
    print("shard done", flush=True)


if __name__ == "__main__":
    main()
