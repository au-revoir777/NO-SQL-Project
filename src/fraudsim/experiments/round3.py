"""
Round 3 experiments (docs/research/round3_protocol.md).

    python -m fraudsim.experiments.round3 capsweep      # R1, seeds 3001-3020
    python -m fraudsim.experiments.round3 step          # R3, seeds 3101-3120
    python -m fraudsim.experiments.round3 scorers       # R4/R5: pipeline scorers (all, LOSO, no-amount)
    python -m fraudsim.experiments.round3 gnn-loso      # R4: GraphSAGE without each scenario
    python -m fraudsim.experiments.round3 loso          # R4, seeds 3201-3220
    python -m fraudsim.experiments.round3 decoy         # R4, seeds 3301-3310
    python -m fraudsim.experiments.round3 prcurve       # R4, seeds 3401-3405
    python -m fraudsim.experiments.round3 amount        # R5, seeds 3501-3520 and 3601-3610
    python -m fraudsim.experiments.round3 latency       # R6, seeds 3701-3705 (run alone)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _append, _merge, make_stream, run_grid
from fraudsim.experiments.tuning import load_tuned
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.features import FEATURE_NAMES
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage
from fraudsim.scoring.train import Row, _matrix, write_rows

OUT = ROOT / "results"
SCEN = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
TRAIN_SCEN = (*SCEN, "scale_sweep")
TRAIN_SEEDS = tuple(range(101, 111))
SCORERS = "results/round3_scorers"
GNN_DIR = "results/round3_gnn"
AMOUNT_FEATURES = ("amount_mean_log", "amount_cv", "near_threshold_frac")
OVERLAP = {"simulation.amount_median": 2000.0}


def _t() -> dict:
    return load_tuned()


def pipe(name: str, hub: dict | None = None, model: str | None = None, alert: float | None = None) -> Method:
    t = _t()
    h = {"edge_threshold": float(t["edge_threshold"])} | (hub or {})
    return Method(name, name, _merge(PROPOSED, {"hub_aware": h}), family="round3",
                  alert_threshold=alert if alert is not None else float(t["alert_threshold"]), model_path=model)


def gnn(name: str, model: str, threshold: float = 0.95, scored: bool = False, alert: float | None = None,
        scorer: str | None = None) -> Method:
    from fraudsim.experiments.w2_baselines import OFF

    return Method(name, name, {**OFF, "gnn": {"node_threshold": threshold, "model_path": model}},
                  engine={"incremental": False}, scored=scored, family="round3",
                  alert_threshold=alert, model_path=scorer)


def rules_own() -> Method:
    from fraudsim.experiments.followups import scored_rules

    return scored_rules()


# ─── R1 cap sweep ─────────────────────────────────────────────────────────────

def capsweep() -> None:
    ms = [pipe("keep_links")] + [pipe(f"cap{c}", {"max_attr_degree": c}) for c in (10, 27, 50, 250)]
    ms.append(rules_own())
    run_grid("round3/capsweep", SCEN, range(3001, 3021), ms, OUT)


# ─── R3 step weight ───────────────────────────────────────────────────────────

def step() -> None:
    ms = [pipe("log_shipped"),
          pipe("step27", {"weight_method": "step_27"}),
          pipe("const_two", {"weight_method": "none", "edge_threshold": 1.0})]
    run_grid("round3/step", SCEN, range(3101, 3121), ms, OUT)


# ─── Pipeline scorers: all scenarios, leave-one-out, no amount features ──────

def _collect(scenario: str, seed: int) -> list[Row]:
    m = pipe("collect")
    stream = make_stream(scenario, seed)
    store = InMemoryGraphStore()
    stage = ScoringStage(scorer=None, record=True)
    eng = DetectionEngine(store, build_detectors(store, m.overrides), tracker=RingTracker(EnsembleConfig()),
                          config=EngineConfig(batch_size=50, full_interval_s=5.0), scorer=stage)
    eng.run(stream.events)
    gen = stream.generator
    start = gen.ts(0.0).timestamp()
    dur = gen.ts().timestamp() - start
    truth = [{u for _, a, u in r.member_history if a == "join"} for r in gen.ledger.rings.values()]
    rows = []
    for r in stage.rows:
        best = max((jaccard(set(r["members"]), g) for g in truth), default=0.0)
        rows.append(Row(scenario, seed, f"r3:{scenario}:{seed}", r["ring_id"], (r["t"] - start) / dur if dur else 0.0,
                        r["status"], int(best >= 0.5), round(best, 4), r["features"]))
    return rows


def _fit(rows: list[Row], path: str, zero: tuple[str, ...] = ()) -> None:
    idx = [FEATURE_NAMES.index(f) for f in zero]
    fit = [r for r in rows if r.t_frac < 0.7]
    cal = [r for r in rows if r.t_frac >= 0.7]
    xf, yf = _matrix(fit)
    xc, yc = _matrix(cal)
    for x in (xf, xc):
        x[:, idx] = 0.0
    s = RingScorer("logistic_regression").fit(xf, yf, xc, yc)
    s.meta.train = {"protocol": "docs/research/round3_protocol.md", "rows": {"fit": len(fit), "cal": len(cal)},
                    "scenarios": sorted({r.scenario for r in rows}), "zeroed_features": list(zero)}
    s.save(ROOT / path)


def scorers() -> None:
    rows: list[Row] = []
    for sc in TRAIN_SCEN:
        for seed in TRAIN_SEEDS:
            rows += _collect(sc, seed)
            print(f"[scorers] {sc} {seed} rows={len(rows)}", flush=True)
    (ROOT / SCORERS).mkdir(parents=True, exist_ok=True)
    write_rows(ROOT / SCORERS / "pipeline_rows.csv", rows)
    _fit(rows, f"{SCORERS}/pipe_all.joblib")
    _fit(rows, f"{SCORERS}/pipe_noamount.joblib", AMOUNT_FEATURES)
    for sc in SCEN:
        _fit([r for r in rows if r.scenario != sc], f"{SCORERS}/pipe_loso_{sc}.joblib")
    s = RingScorer.load(ROOT / f"{SCORERS}/pipe_noamount.joblib")
    lr = s.model.named_steps["lr"]
    coef = {f: float(lr.coef_[0][FEATURE_NAMES.index(f)]) for f in AMOUNT_FEATURES}
    (ROOT / SCORERS / "noamount_check.json").write_text(json.dumps({"coef_of_zeroed_features": coef}, indent=1))
    print("zeroed coefficients", coef)


# ─── GraphSAGE leave-one-scenario-out ─────────────────────────────────────────

def gnn_loso() -> None:
    import torch

    from fraudsim.detectors.external import make_sage
    from fraudsim.experiments.w2_baselines import gnn_snapshots

    cache: dict[str, list] = {}
    for sc in TRAIN_SCEN:
        g = []
        for seed in TRAIN_SEEDS:
            g += gnn_snapshots(sc, seed)[0]
        cache[sc] = g
        print(f"[gnn-loso] snapshots {sc}: {len(g)}", flush=True)
    for left in SCEN:
        if (ROOT / GNN_DIR / f"graphsage_loso_{left}.pt").exists():  # resumable
            continue
        torch.manual_seed(0)
        np.random.seed(0)
        graphs = [x for sc, gs in cache.items() if sc != left for x in gs]
        xs = np.concatenate([g[0] for g in graphs])
        mean, std = xs.mean(0), xs.std(0) + 1e-6
        n_pos = sum(float(g[2].sum()) for g in graphs)
        n = sum(g[3] for g in graphs)
        model = make_sage(hidden=64)
        opt = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=5e-4)
        loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor((n - n_pos) / max(n_pos, 1.0)))
        tens = [(torch.from_numpy((x - mean) / std), torch.from_numpy(ei), torch.from_numpy(y), k)
                for x, ei, y, k in graphs]
        t0 = time.perf_counter()
        for ep in range(40):
            model.train()
            for i in np.random.permutation(len(tens)):
                x, ei, y, k = tens[i]
                opt.zero_grad()
                loss = loss_fn(model(x, ei)[:k], y)
                loss.backward()
                opt.step()
        path = ROOT / GNN_DIR / f"graphsage_loso_{left}.pt"
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "hparams": {"hidden": 64, "dropout": 0.2},
                    "mean": mean.astype(np.float32), "std": std.astype(np.float32)}, path)
        (path.with_suffix(".json")).write_text(json.dumps({"left_out": left, "snapshots": len(graphs),
                                                           "wall_s": round(time.perf_counter() - t0, 1)}))
        print(f"[gnn-loso] trained without {left} ({time.perf_counter() - t0:.0f}s)", flush=True)


def loso() -> None:
    from fraudsim.experiments.w2_baselines import GNN_MODEL

    for sc in SCEN:
        ms = [gnn("gnn_all", GNN_MODEL), gnn("gnn_loso", f"{GNN_DIR}/graphsage_loso_{sc}.pt"),
              pipe("pipe_all", model=f"{SCORERS}/pipe_all.joblib"),
              pipe("pipe_loso", model=f"{SCORERS}/pipe_loso_{sc}.joblib")]
        run_grid("round3/loso", [sc], range(3201, 3221), ms, OUT)


# ─── Decoy sweep with GraphSAGE ───────────────────────────────────────────────

def _w2_methods() -> list[Method]:
    from fraudsim.experiments.w2_baselines import SELECTION, _parse, make

    sel = json.loads(SELECTION.read_text())
    out = []
    for key in ("gnn_unscored", "gnn", "hybrid"):
        m, v, a, s = _parse(sel[key]["method"])
        x = make(m, v, a, s)
        x.name = f"w2_{key}"
        out.append(x)
    return out


def decoy() -> None:
    from fraudsim.experiments.learned_baselines import sweep_overrides
    from fraudsim.experiments.suite import tuned_proposed

    ms = [tuned_proposed(), *_w2_methods()]
    for v in (0, 1, 2, 4, 8):
        run_grid("round3/decoy", ["high_noise"], range(3301, 3311), ms, OUT,
                 scenario_overrides=sweep_overrides("decoy_edges", v), extra_columns={"decoys": v})


# ─── Operating-point sweep (precision at matched recall) ─────────────────────

def prcurve() -> None:
    from fraudsim.experiments.suite import tuned_proposed
    from fraudsim.experiments.w2_baselines import GNN_MODEL, make

    ms = []
    for a in (0.3, 0.5, 0.7, 0.8, 0.9):
        p = tuned_proposed(f"proposed_a{a}")
        p.alert_threshold = a
        ms.append(p)
        h = make("hybrid", 0.9, a)
        h.name = f"hybrid_a{a}"
        ms.append(h)
        g = make("gnn", 0.9, a)
        g.name = f"gnn_scored_a{a}"
        ms.append(g)
    for t in (0.8, 0.9, 0.95, 0.97, 0.99):
        ms.append(gnn(f"gnn_unscored_t{t}", GNN_MODEL, t))
    run_grid("round3/prcurve", SCEN, range(3401, 3406), ms, OUT)


# ─── R5 amount features ───────────────────────────────────────────────────────

def amount() -> None:
    from fraudsim.experiments.w2_baselines import GNN_MODEL

    a = [pipe("pipe_all", model=f"{SCORERS}/pipe_all.joblib"),
         pipe("pipe_noamount", model=f"{SCORERS}/pipe_noamount.joblib")]
    run_grid("round3/amount_ablation", SCEN, range(3501, 3521), a, OUT)
    b = a + [gnn("gnn_unscored", GNN_MODEL), rules_own()]
    run_grid("round3/amount_overlap", SCEN, range(3601, 3611), b, OUT, scenario_overrides=OVERLAP)


# ─── R6 latency in one environment ────────────────────────────────────────────

def latency() -> None:
    from fraudsim.experiments.timer_baselines import scale_overrides
    from fraudsim.metrics.evaluation import detect_ms

    out = OUT / "round3" / "latency"
    out.mkdir(parents=True, exist_ok=True)
    off = {"static_cypher": {"enabled": False}, "community": {"enabled": False}}
    modes = {"incremental": {"incremental": True}, "timer_5": {"incremental": False, "full_timer_s": 5.0}}
    for n in (1000, 5000, 10000, 20000):
        for seed in range(3701, 3706):
            stream = make_stream("scale_sweep", seed, scale_overrides(n))
            start = stream.generator.ts(0.0)
            head = [e for e in stream.events if (e.ts - start).total_seconds() < 10]
            tail = stream.events[len(head):]
            span = (tail[-1].ts - tail[0].ts).total_seconds()
            for mode, cfg in modes.items():
                store = InMemoryGraphStore()
                store.apply(head)
                eng = DetectionEngine(store, build_detectors(store, off), config=EngineConfig(**cfg))
                eng.run(tail)
                det = sorted(detect_ms(r) for r in eng.reports if r.detector_ms)
                regions = sorted(r.region for r in eng.reports if r.detector_ms)
                _append(out / "results.csv", {
                    "experiment": "round3_latency", "users": n, "seed": seed, "mode": mode,
                    "stream_digest": stream.generator.digest[:16], "passes": len(det),
                    "region_p50": regions[len(regions) // 2] if regions else 0,
                    "detect_ms_p50": round(det[len(det) // 2], 3) if det else 0.0,
                    "detect_ms_sum": round(sum(det), 3), "sim_s": round(span, 3),
                    "ms_per_sim_s": round(sum(det) / span, 3)})
                print(f"[latency] {n} {seed} {mode} {sum(det) / span:.0f} ms/sim-s", flush=True)


if __name__ == "__main__":
    {"capsweep": capsweep, "step": step, "scorers": scorers, "gnn-loso": gnn_loso, "loso": loso,
     "decoy": decoy, "prcurve": prcurve, "amount": amount, "latency": latency}[sys.argv[1]]()
