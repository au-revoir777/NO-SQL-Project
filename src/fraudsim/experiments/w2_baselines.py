"""
W2/W3: external baselines with their own scorers, tuned with equal budget on validation seeds,
compared with the proposed pipeline on fresh test seeds (docs/research/w2_protocol.md).

    python -m fraudsim.experiments.w2_baselines train-gnn
    python -m fraudsim.experiments.w2_baselines train-scorers [--methods a,b]
    python -m fraudsim.experiments.w2_baselines tune [--methods a,b]
    python -m fraudsim.experiments.w2_baselines select
    python -m fraudsim.experiments.w2_baselines run [--methods a,b]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _merge, make_stream, run_grid
from fraudsim.experiments.provenance import recorded
from fraudsim.graph.store import InMemoryGraphStore, event_t
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage
from fraudsim.scoring.train import Row, _matrix, write_rows

TRAIN_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift", "scale_sweep")
SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
TRAIN_SEEDS = tuple(range(101, 111))
VALIDATION_SEEDS = (301, 302, 303)
TEST_SEEDS = tuple(range(2101, 2121))
ALERT_GRID = (0.2, 0.3, 0.5, 0.7, 0.8, 0.9)
FIT_FRACTION = 0.7
OUT = ROOT / "results"
SCORERS = "results/w2_scorers"
GNN_MODEL = "results/w2_gnn/graphsage.pt"
SELECTION = ROOT / "results/w2_tuning/selected.json"

OFF = {k: {"enabled": False} for k in ("static_cypher", "hub_aware", "temporal_cycle", "smurfing", "community")}
WHOLE = {"incremental": False}  # whole graph every batch

# method -> (structural parameter name, grid, default, overrides builder, engine)
STRUCT: dict[str, tuple[str, tuple, Any]] = {
    "peeling": ("min_block_score", (0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8, 1.0, 1.3), 0.5),
    "leiden": ("resolution", (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0), 1.0),
    "louvain": ("resolution", (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0), 1.0),
    "gnn": ("node_threshold", (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95), 0.5),
    # rules: cap x cycle rule on/off, 7 x 2 = 14 structural configurations
    "rules": ("cap_cycle", tuple(f"{c}_{q}" for c in (3, 5, 10, 20, 50, 100, 200) for q in (1, 0)), "10_1"),
}


def overrides(method: str, value: Any) -> tuple[dict, dict]:
    if method == "peeling":
        return {**OFF, "peeling": {"min_block_score": float(value)}}, WHOLE
    if method == "leiden":
        return {**OFF, "leiden": {"resolution": float(value)}}, WHOLE
    if method == "louvain":
        return {**OFF, "community": {"algorithm": "louvain", "resolution": float(value)}}, {}
    if method == "gnn":
        return {**OFF, "gnn": {"node_threshold": float(value), "model_path": GNN_MODEL}}, WHOLE
    if method == "rules":
        cap, cyc = str(value).split("_")
        return {**OFF, "static_cypher": {"enabled": True, "max_degree_cap": int(cap),
                                          "enable_q3_money_cycle": cyc == "1"}}, {}
    raise ValueError(method)


def make(method: str, value: Any, alert: float | None, scored: bool = True, tag: str = "") -> Method:
    ov, eng = overrides(method, value)
    name = f"w2_{method}_{value}" + (f"_a{alert}" if scored else "_unscored") + tag
    return Method(name, name, ov, engine=eng, scored=scored, family=f"w2_{method}",
                  alert_threshold=alert if scored else None,
                  model_path=f"{SCORERS}/{method}.joblib" if scored else None)


# ─── GraphSAGE training ───────────────────────────────────────────────────────


def _labels_at(ledger, t_epoch: float) -> set[str]:
    pos: set[str] = set()
    for r in ledger.rings.values():
        if r.spawn_ts is None or r.spawn_ts.timestamp() > t_epoch:
            continue
        if r.dissolve_ts is not None and r.dissolve_ts.timestamp() < t_epoch:
            continue
        cur: set[str] = set()
        for ts, action, u in sorted(r.member_history, key=lambda x: x[0]):
            if ts.timestamp() > t_epoch:
                break
            (cur.add if action == "join" else cur.discard)(u)
        pos |= cur
    return pos


def gnn_snapshots(scenario: str, seed: int, every_s: float = 5.0):
    from fraudsim.detectors.external import graph_tensors

    stream = make_stream(scenario, seed)
    store = InMemoryGraphStore()
    eng = DetectionEngine(store, [], config=EngineConfig(batch_size=50))
    out, last = [], None
    window = eng.cfg.window_s
    for batch in eng.batches(stream.events):
        store.apply(batch)
        now = event_t(batch[-1])
        if last is not None and now - last < every_s:
            continue
        last = now
        view = store.full_view(now - window, now)
        users, x, ei = graph_tensors(view, store.joined(set(view.users)))
        if not users:
            continue
        pos = _labels_at(stream.generator.ledger, now)
        y = np.array([1.0 if u in pos else 0.0 for u in users], dtype=np.float32)
        out.append((x, ei, y, len(users)))
    return out, stream.generator.digest[:16]


def train_gnn(epochs: int = 40, hidden: int = 64, lr: float = 0.005) -> None:
    import torch

    from fraudsim.detectors.external import make_sage

    torch.manual_seed(0)
    np.random.seed(0)
    started = time.perf_counter()
    graphs, digests = [], {}
    for sc in TRAIN_SCENARIOS:
        for seed in TRAIN_SEEDS:
            g, d = gnn_snapshots(sc, seed)
            graphs += g
            digests[f"{sc}:{seed}"] = d
            print(f"[gnn] {sc} {seed}: {len(g)} snapshots", flush=True)
    xs = np.concatenate([g[0] for g in graphs])
    mean, std = xs.mean(0), xs.std(0) + 1e-6
    n_pos = sum(float(g[2].sum()) for g in graphs)
    n_users = sum(g[3] for g in graphs)
    pos_weight = torch.tensor((n_users - n_pos) / max(n_pos, 1.0))
    model = make_sage(hidden=hidden)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=5e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    tens = [(torch.from_numpy((x - mean) / std), torch.from_numpy(ei), torch.from_numpy(y), n)
            for x, ei, y, n in graphs]
    hist = []
    for ep in range(epochs):
        model.train()
        order = np.random.permutation(len(tens))
        tot = 0.0
        for i in order:
            x, ei, y, n = tens[i]
            opt.zero_grad()
            logit = model(x, ei)[:n]
            loss = loss_fn(logit, y)
            loss.backward()
            opt.step()
            tot += float(loss)
        hist.append(round(tot / len(tens), 4))
        print(f"[gnn] epoch {ep + 1}: loss {hist[-1]}", flush=True)
    path = ROOT / GNN_MODEL
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hparams": {"hidden": hidden, "dropout": 0.2},
                "mean": mean.astype(np.float32), "std": std.astype(np.float32)}, path)
    meta = {"protocol": "docs/research/w2_protocol.md", "scenarios": TRAIN_SCENARIOS,
            "train_seeds": TRAIN_SEEDS, "snapshots": len(graphs), "user_rows": int(n_users),
            "positive_rows": int(n_pos), "epochs": epochs, "lr": lr, "hidden": hidden,
            "loss_by_epoch": hist, "wall_s": round(time.perf_counter() - started, 1),
            "stream_digests": digests, "torch": torch.__version__}
    (path.parent / "training.json").write_text(json.dumps(meta, indent=1))


# ─── Own scorers ──────────────────────────────────────────────────────────────


def collect_rows(method: str, scenario: str, seed: int) -> tuple[list[Row], dict]:
    ov, eng_cfg = overrides(method, STRUCT[method][2])
    stream = make_stream(scenario, seed)
    store = InMemoryGraphStore()
    stage = ScoringStage(scorer=None, record=True)
    engine = DetectionEngine(store, build_detectors(store, ov), tracker=RingTracker(EnsembleConfig()),
                             config=EngineConfig(batch_size=50, full_interval_s=5.0, **eng_cfg),
                             scorer=stage)
    engine.run(stream.events)
    gen = stream.generator
    start = gen.ts(0.0).timestamp()
    duration = gen.ts().timestamp() - start
    truth = [{u for _, a, u in r.member_history if a == "join"} for r in gen.ledger.rings.values()]
    rows = []
    for r in stage.rows:
        best = max((jaccard(set(r["members"]), gt) for gt in truth), default=0.0)
        rows.append(Row(scenario, seed, f"w2:{method}:{scenario}:{seed}", r["ring_id"],
                        (r["t"] - start) / duration if duration else 0.0, r["status"],
                        int(best >= 0.5), round(best, 4), r["features"]))
    return rows, {"scenario": scenario, "seed": seed, "stream_digest": gen.digest[:16],
                  "rows": len(rows), "positives": sum(x.label for x in rows)}


def train_scorer(method: str) -> None:
    out_dir = OUT / "w2_scorers"
    with recorded(out_dir, f"w2_scorer_{method}", {"method": method, "train_seeds": TRAIN_SEEDS,
                                                    "scenarios": TRAIN_SCENARIOS}):
        rows, runs = [], []
        for sc in TRAIN_SCENARIOS:
            for seed in TRAIN_SEEDS:
                r, info = collect_rows(method, sc, seed)
                rows += r
                runs.append(info)
                print(f"[scorer {method}] {sc} {seed}: {info['rows']} rows, {info['positives']} pos", flush=True)
        fit = [r for r in rows if r.t_frac < FIT_FRACTION]
        cal = [r for r in rows if r.t_frac >= FIT_FRACTION]
        scorer = RingScorer("logistic_regression").fit(*_matrix(fit), *_matrix(cal))
        scorer.meta.train = {"method": method, "structural_default": STRUCT[method][2],
                             "scenarios": list(TRAIN_SCENARIOS), "train_seeds": list(TRAIN_SEEDS),
                             "rows": {"fit": len(fit), "calibration": len(cal)}, "runs": runs}
        scorer.save(ROOT / f"{SCORERS}/{method}.joblib")
        write_rows(out_dir / f"{method}_rows.csv", rows)


# ─── Tuning, selection, evaluation ────────────────────────────────────────────


def tune(methods: list[str]) -> None:
    for m in methods:
        name, grid, _ = STRUCT[m]
        ms = [make(m, v, a) for v in grid for a in ALERT_GRID]
        if m == "gnn":
            ms += [make(m, v, None, scored=False) for v in grid]
        run_grid(f"w2_tuning/{m}", SCENARIOS, VALIDATION_SEEDS, ms, OUT)


def select() -> dict:
    out: dict[str, Any] = {}
    for m in STRUCT:
        p = OUT / f"w2_tuning/{m}/results.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        df["f1"] = df["f1"].fillna(0)
        f = df.groupby("method")["f1"].mean()
        scored = f[[i for i in f.index if "_unscored" not in i]]
        best = scored.idxmax()
        out[m] = {"method": best, "val_f1": round(float(scored[best]), 4)}
        if m == "rules":  # per-scenario selection (strongest rule baseline)
            per = df[~df["method"].str.contains("_unscored")].groupby(["scenario", "method"])["f1"].mean()
            out["rules_per_scenario"] = {s: per[s].idxmax() for s in SCENARIOS}
        if m == "gnn":
            un = f[[i for i in f.index if "_unscored" in i]]
            out["gnn_unscored"] = {"method": un.idxmax(), "val_f1": round(float(un.max()), 4)}
    SELECTION.parent.mkdir(parents=True, exist_ok=True)
    SELECTION.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    return out


def _parse(name: str) -> tuple[str, Any, float | None, bool]:
    body = name[len("w2_"):]
    m, rest = body.split("_", 1)
    if m == "rules":
        cap, cyc, tail = rest.split("_", 2)
        value, tail = f"{cap}_{cyc}", tail
    else:
        value, tail = rest.split("_", 1)
    if tail == "unscored":
        return m, value, None, False
    return m, value, float(tail[1:]), True


def run(methods: list[str]) -> None:
    sel = json.loads(SELECTION.read_text())
    for m in methods:
        if m == "proposed":
            from fraudsim.experiments.tuning import load_tuned

            t = load_tuned()
            ov = _merge(PROPOSED, {"hub_aware": {"edge_threshold": float(t["edge_threshold"])}})
            meth = [Method("proposed", "proposed (shipped)", ov, family="proposed",
                           alert_threshold=float(t["alert_threshold"]))]
        elif m == "gb_louvain":
            from fraudsim.experiments.learned_baselines import selected_threshold, tabular_gb

            meth = [tabular_gb(selected_threshold())]
        elif m == "rules_per_scenario":
            for sc, name in sel["rules_per_scenario"].items():
                mm, v, a, s = _parse(name)
                x = make(mm, v, a, s)
                x.name, x.label = "w2_rules_per_scenario", f"rules per-scenario ({name})"
                run_grid("w2_eval/rules_per_scenario", [sc], TEST_SEEDS, [x], OUT)
            continue
        else:
            key = "gnn_unscored" if m == "gnn_unscored" else m
            mm, v, a, s = _parse(sel[key]["method"])
            meth = [make(mm, v, a, s)]
            meth[0].name = f"w2_{key}"
        run_grid(f"w2_eval/{m}", SCENARIOS, TEST_SEEDS, meth, OUT)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["train-gnn", "train-scorers", "tune", "select", "run"])
    ap.add_argument("--methods", default=",".join(STRUCT))
    a = ap.parse_args()
    ms = a.methods.split(",")
    if a.step == "train-gnn":
        train_gnn()
    elif a.step == "train-scorers":
        for m in ms:
            train_scorer(m)
    elif a.step == "tune":
        tune(ms)
    elif a.step == "select":
        select()
    else:
        run(ms)


if __name__ == "__main__":
    main()
