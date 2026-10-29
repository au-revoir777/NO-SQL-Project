"""
Round 4 experiments (docs/research/round4_protocol.md).

    python -m fraudsim.experiments.round4 train-bwgnn      # BWGNN on the GraphSAGE snapshots
    python -m fraudsim.experiments.round4 tune-bwgnn       # validation 301-303
    python -m fraudsim.experiments.round4 select-bwgnn
    python -m fraudsim.experiments.round4 test-bwgnn       # 6001-6020
    python -m fraudsim.experiments.round4 trigger-ref      # hold-out 201-205 references for G-amount / G-score
    python -m fraudsim.experiments.round4 guard S0 ... S6  # I3 shift blocks
    python -m fraudsim.experiments.round4 traces           # trigger statistics per batch on the shift blocks
"""

from __future__ import annotations

import argparse
import json
import time
from statistics import median
from typing import Any

import joblib
import numpy as np
import pandas as pd

from fraudsim.detectors import external as ext
from fraudsim.experiments import anchor as an
from fraudsim.experiments import evidgnn as eg
from fraudsim.experiments.harness import ROOT, Method, make_stream, run_grid
from fraudsim.graph.store import InMemoryGraphStore

OUT = ROOT / "results"
D = "results/round4"
CACHE = ROOT / ".cache" / "round4"
SCEN = eg.SCEN
BW_MODEL = f"{D}/bwgnn.pt"
BW_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.97, 0.98, 0.99, 0.995)
K = an.K
Q = an.QUANTILE
AMOUNT_WINDOW = 200


# ─── I2.5 BWGNN ───────────────────────────────────────────────────────────────

def sage_snapshots() -> list:
    """The GraphSAGE baseline's training snapshots (seeds 101-110 x six scenarios), cached on disk."""
    from fraudsim.experiments.w2_baselines import TRAIN_SCENARIOS, gnn_snapshots

    p = CACHE / "sage_snapshots.joblib"
    if p.exists():
        return joblib.load(p)
    graphs = []
    for sc in TRAIN_SCENARIOS:
        for seed in range(101, 111):
            graphs += gnn_snapshots(sc, seed)[0]
        print(f"[bwgnn] snapshots {sc}: {len(graphs)}", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    joblib.dump(graphs, p)
    return graphs


def train_bwgnn(epochs: int = 100, lr: float = 0.01) -> None:
    import torch

    torch.set_num_threads(1)
    torch.manual_seed(0)
    np.random.seed(0)
    graphs = sage_snapshots()
    xs = np.concatenate([g[0] for g in graphs])
    mean, std = xs.mean(0), xs.std(0) + 1e-6
    n_pos = sum(float(g[2].sum()) for g in graphs)
    n = sum(g[3] for g in graphs)
    model = ext.make_bwgnn(hidden=64, order=2)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor((n - n_pos) / max(n_pos, 1.0)))
    tens = [(torch.from_numpy((x - mean) / std), torch.from_numpy(ei), torch.from_numpy(y), k)
            for x, ei, y, k in graphs]
    t0 = time.perf_counter()
    hist = []
    for ep in range(epochs):
        model.train()
        tot = 0.0
        for i in np.random.permutation(len(tens)):
            x, ei, y, k = tens[i]
            opt.zero_grad()
            loss = loss_fn(model(x, ei)[:k], y)
            loss.backward()
            opt.step()
            tot += float(loss)
        hist.append(round(tot / len(tens), 4))
        if ep % 10 == 9:
            print(f"[bwgnn] epoch {ep + 1}/{epochs} loss {hist[-1]}", flush=True)
    path = ROOT / BW_MODEL
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hparams": {"arch": "bwgnn", "hidden": 64, "order": 2},
                "mean": mean.astype(np.float32), "std": std.astype(np.float32)}, path)
    path.with_suffix(".json").write_text(json.dumps({
        "protocol": "docs/research/round4_protocol.md", "model": "BWGNN (homo), order 2, hidden 64",
        "reference_code": "github.com/squareRoot3/Rethinking-Anomaly-Detection BWGNN.py",
        "snapshots": len(graphs), "user_rows": int(n), "positive_rows": int(n_pos), "epochs": epochs,
        "lr": lr, "loss_by_epoch": hist, "wall_s": round(time.perf_counter() - t0, 1),
        "torch": torch.__version__}, indent=1))
    print(f"[bwgnn] done in {time.perf_counter() - t0:.0f}s", flush=True)


def bwgnn_method(threshold: float, name: str | None = None) -> Method:
    m = eg.gnn_method(threshold, name=name or f"bwgnn_{threshold}")
    m.overrides["gnn"]["model_path"] = BW_MODEL
    m.overrides["gnn"]["name"] = "BWGNN"
    m.family = "bwgnn"
    return m


def tune_bwgnn() -> None:
    eg.run_methods("round4_tuning/bwgnn", SCEN, eg.VAL_SEEDS, [bwgnn_method(v) for v in BW_GRID])


def select_bwgnn() -> dict:
    df = pd.read_csv(OUT / "round4_tuning/bwgnn/results.csv")
    best, f1 = eg._best(df)
    out = {"protocol": "docs/research/round4_protocol.md", "bwgnn": {"method": best, "val_f1": f1,
                                                                    "node_threshold": eg._thr(best)[0]}}
    (ROOT / D).mkdir(parents=True, exist_ok=True)
    (ROOT / D / "selected.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def test_bwgnn() -> None:
    sel = json.loads((ROOT / D / "selected.json").read_text())["bwgnn"]
    ms = [bwgnn_method(sel["node_threshold"], "bwgnn")]
    ms += eg.systems(json.loads(eg.SELECTED.read_text()), ["gnn_unscored", "proposed"])
    for m in ms:
        eg.run_methods(f"round4_bwgnn/{m.name}", SCEN, tuple(range(6001, 6021)), [m])
    an.run("round4_bwgnn/anchor", SCEN, tuple(range(6001, 6021)), an.systems(["anchor"]))


# ─── I3 trigger statistics ────────────────────────────────────────────────────

REF: dict[str, Any] = {}


def _ks(a: np.ndarray, b: np.ndarray) -> float:
    from scipy.stats import ks_2samp

    if len(a) < 5 or len(b) < 5:
        return 0.0
    return float(ks_2samp(a, b).statistic)


def stats_hook(det, view, scores) -> None:
    """Per scoring call: KS D of recent transfer amounts and of GNN scores against the references."""
    amounts = np.array([t.amount for t in sorted(view.txns, key=lambda t: t.t)[-AMOUNT_WINDOW:]])
    ps = np.fromiter(scores.values(), float) if scores else np.array([])
    h = det.__dict__.setdefault("drift_history", {"amount": [], "score": []})
    if "amount_ref" in REF:
        h["amount"].append(_ks(amounts, REF["amount_ref"]))
        h["score"].append(_ks(ps, REF["score_ref"]))
    else:  # collecting the reference samples themselves
        REF.setdefault("_amounts", []).append(amounts)
        REF.setdefault("_scores", []).append(ps)


def stat(det, kind: str) -> float | None:
    if det is None:
        return None
    if kind == "flag":
        return an.guard_stat(det)
    hist = det.__dict__.get("drift_history", {}).get(kind, [])
    return float(median(hist[-K:])) if hist else None


def _gnn_only_engine(stream):
    from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
    from fraudsim.experiments.w2_baselines import GNN_MODEL

    off = {k: {"enabled": False} for k in ("static_cypher", "hub_aware", "temporal_cycle", "smurfing", "community")}
    store = InMemoryGraphStore()
    eng = DetectionEngine(store, build_detectors(store, {**off, "gnn": {
        "model_path": GNN_MODEL, "node_threshold": 0.95, "as_full_detector": True}}),
        config=EngineConfig(batch_size=50, full_interval_s=0.0))
    return eng, an._gnn(eng)


def trigger_reference() -> dict:
    """Pooled hold-out samples, then the per-batch D of each hold-out stream against them; tau = q99.5."""
    ext.DETECT_HOOKS[:] = [stats_hook]
    REF.clear()
    streams = [(sc, s) for sc in eg.TRAIN_SCEN for s in an.HOLDOUT]
    for sc, seed in streams:  # pass 1: samples
        stream = make_stream(sc, seed)
        eng, _ = _gnn_only_engine(stream)
        for b in eng.batches(stream.events):
            eng.process(b)
    rng = np.random.default_rng(0)
    amounts = np.concatenate([a for a in REF.pop("_amounts") if len(a)])
    scores = np.concatenate([a for a in REF.pop("_scores") if len(a)])
    REF["amount_ref"] = rng.choice(amounts, min(5000, len(amounts)), replace=False)
    REF["score_ref"] = rng.choice(scores, min(5000, len(scores)), replace=False)
    vals = {"amount": [], "score": []}
    for sc, seed in streams:  # pass 2: statistics
        stream = make_stream(sc, seed)
        eng, det = _gnn_only_engine(stream)
        for b in eng.batches(stream.events):
            eng.process(b)
            for k in vals:
                v = stat(det, k)
                if v is not None:
                    vals[k].append(v)
        print(f"[trigger-ref] {sc} {seed}", flush=True)
    out = {"protocol": "docs/research/round4_protocol.md", "K": K, "quantile": Q, "amount_window": AMOUNT_WINDOW,
           "tau": {k: float(np.quantile(v, Q)) for k, v in vals.items()},
           "median": {k: float(np.median(v)) for k, v in vals.items()}, "n_batches": len(vals["amount"])}
    (ROOT / D).mkdir(parents=True, exist_ok=True)
    np.savez(ROOT / D / "trigger_reference.npz", amount_ref=REF["amount_ref"], score_ref=REF["score_ref"])
    (ROOT / D / "trigger_reference.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out), flush=True)
    return out


def load_reference() -> dict:
    z = np.load(ROOT / D / "trigger_reference.npz")
    REF.clear()
    REF["amount_ref"], REF["score_ref"] = z["amount_ref"], z["score_ref"]
    ref = json.loads((ROOT / D / "trigger_reference.json").read_text())
    ref["tau"]["flag"] = an.tau()
    return ref


# ─── I3 shift blocks ──────────────────────────────────────────────────────────

class TriggerScorer(an.GuardedScorer):
    """GuardedScorer whose trigger kind and threshold travel with it (one per method)."""

    def __init__(self, *a, kind: str = "flag", tau: float | None = None, **k) -> None:
        super().__init__(*a, **k)
        self.kind, self.tau = kind, tau


class TriggerStage(an.AnchorStage):
    def featurize(self, engine, ring, others, now_t, since_t):
        feats, view, joined = super().featurize(engine, ring, others, now_t, since_t)
        sc = self.scorer
        kind = getattr(sc, "kind", "never")
        if kind == "always":
            fire = True
        elif kind == "never":
            fire = False
        else:
            v = stat(an._gnn(engine), kind)
            fire = v is not None and v > sc.tau
        vec = feats.to_vector()[:-1] + [1.0 if fire else 0.0]
        return eg._Feats(feats._b, vec[19:], (*eg.GNN_STATS, *an.ANCHOR_STATS, "guard_flag")), view, joined


TRIGGERS = ("flag", "amount", "score", "never", "always")


def trigger_methods() -> list[Method]:
    s = json.loads(an.SEL.read_text())["anchor"]
    out = []
    for kind in TRIGGERS:
        m = an.method(s["node_threshold"], s["alert"], "anchor", name=f"trig_{kind}")
        m.model_path = f"results/anchor/fused_anchor.joblib#{kind}"
        out.append(m)
    return out


SHIFTS: dict[str, tuple[tuple[str, ...], tuple[int, ...], dict]] = {
    "S0": (SCEN, tuple(range(6101, 6106)), {}),
    "S1": (SCEN, tuple(range(6111, 6116)), {"simulation.amount_median": 2000}),
    "S2": (SCEN, tuple(range(6121, 6126)), {"simulation.target_event_rate": 30}),
    "S3": (SCEN, tuple(range(6131, 6136)), {"simulation.heavy_tail_alpha": 1.3}),
    "S4": (("hub_heavy",), tuple(range(6141, 6146)), "hub2000"),  # type: ignore[dict-item]
    "S5": (SCEN, tuple(range(6151, 6156)), {"random_rings.size_min": 8, "random_rings.size_max": 12}),
    "S6": (SCEN, tuple(range(6161, 6166)), "ring_amounts"),  # type: ignore[dict-item]
}


def shift_overrides(ov) -> dict:
    if ov == "hub2000":
        from fraudsim.experiments.large_hubs import overrides as hub_ov

        return hub_ov(2000)
    if ov == "ring_amounts":
        from fraudsim.simulator.config import EvasionMode

        return {f"simulation.evasion_params.{m.value}.amount_mult": 0.1 for m in EvasionMode}
    return dict(ov)


def run_triggers(experiment: str, scenarios, seeds, scen_ov: dict) -> None:
    """All five trigger variants in one grid, so the GNN scores of a stream are computed once."""
    from fraudsim.detectors import evidgnn as det
    from fraudsim.experiments import harness
    from fraudsim.experiments.w2_baselines import skip_explanations
    from fraudsim.scoring.scorer import RingScorer

    skip_explanations()
    ref = load_reference()
    ext.DETECT_HOOKS[:] = [stats_hook]
    shipped = RingScorer.load(ROOT / "models/ring_scorer_lr.joblib")
    s = json.loads(an.SEL.read_text())["anchor"]
    from fraudsim.experiments.tuning import load_tuned

    theta_s = float(load_tuned()["alert_threshold"])

    def load(p):
        p = str(p)
        if "fused_anchor.joblib#" in p:
            kind = p.split("#")[1]
            fused = eg.load_fused(ROOT / "results/anchor/fused_anchor.joblib")
            return TriggerScorer(fused, shipped, 24, float(s["alert"]), theta_s, kind=kind,
                                 tau=ref["tau"].get(kind))
        return orig_load(p)

    orig_stage, orig_load, orig_stream = harness.ScoringStage, harness.RingScorer.load, harness.make_stream

    def fresh(*a, **k):
        det.SCORE_CACHE = {}
        return orig_stream(*a, **k)

    harness.ScoringStage = TriggerStage  # type: ignore[misc]
    harness.RingScorer.load = staticmethod(load)  # type: ignore[method-assign]
    harness.make_stream = fresh  # type: ignore[assignment]
    try:
        run_grid(experiment, scenarios, seeds, trigger_methods(), OUT,
                 scenario_overrides=scen_ov or None)
    finally:
        harness.ScoringStage, harness.RingScorer.load, harness.make_stream = orig_stage, orig_load, orig_stream
        det.SCORE_CACHE = None
        ext.DETECT_HOOKS[:] = []


def guard(block: str) -> None:
    scenarios, seeds, ov = SHIFTS[block]
    so = shift_overrides(ov)
    run_triggers(f"round4_guard/{block}/triggers", scenarios, seeds, so)
    refs = eg.systems(json.loads(eg.SELECTED.read_text()), ["gnn_unscored", "proposed", "rules"])
    for m in refs:
        eg.run_methods(f"round4_guard/{block}/{m.name}", scenarios, seeds, [m], scenario_overrides=so or None)


def traces() -> None:
    """Per batch, all three trigger statistics on every shift-block stream (GNN only; no detectors)."""
    ref = load_reference()
    ext.DETECT_HOOKS[:] = [stats_hook]
    rows = []
    for block, (scenarios, seeds, ov) in SHIFTS.items():
        so = shift_overrides(ov)
        for sc in scenarios:
            for seed in seeds:
                stream = make_stream(sc, seed, so or None)
                eng, det = _gnn_only_engine(stream)
                start = stream.generator.ts(0.0).timestamp()
                first = {k: None for k in ("flag", "amount", "score")}
                fired = {k: 0 for k in first}
                nb = 0
                for b in eng.batches(stream.events):
                    eng.process(b)
                    nb += 1
                    t = b[-1].ts.timestamp() - start
                    for k in first:
                        v = stat(det, k)
                        if v is not None and v > ref["tau"][k]:
                            fired[k] += 1
                            if first[k] is None:
                                first[k] = t
                rows.append({"block": block, "scenario": sc, "seed": seed, "batches": nb,
                             **{f"first_{k}": first[k] for k in first},
                             **{f"frac_{k}": fired[k] / max(nb, 1) for k in fired}})
        print(f"[traces] {block} done", flush=True)
    ext.DETECT_HOOKS[:] = []
    (ROOT / D).mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(ROOT / D / "trigger_traces.csv", index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("blocks", nargs="*")
    a = ap.parse_args()
    if a.step == "train-bwgnn":
        train_bwgnn()
    elif a.step == "tune-bwgnn":
        tune_bwgnn()
    elif a.step == "select-bwgnn":
        select_bwgnn()
    elif a.step == "test-bwgnn":
        test_bwgnn()
    elif a.step == "trigger-ref":
        trigger_reference()
    elif a.step == "guard":
        for b in a.blocks:
            guard(b)
    elif a.step == "traces":
        traces()


if __name__ == "__main__":
    main()
