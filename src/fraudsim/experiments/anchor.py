"""
AnchorPipe: evidence-anchored, shift-guarded GNN fusion (docs/research/anchor_protocol.md).

    python -m fraudsim.experiments.anchor reference        # guard reference on hold-out 201-205
    python -m fraudsim.experiments.anchor fused-train      # anchored fused scorer (out-of-fold GraphSAGE)
    python -m fraudsim.experiments.anchor tune             # validation 301-303
    python -m fraudsim.experiments.anchor dev              # development shifts 5001-5005 (guard check)
    python -m fraudsim.experiments.anchor select
    python -m fraudsim.experiments.anchor test T1|T2|T3|T4
"""

from __future__ import annotations

import argparse
import json
from statistics import median
from typing import Any

import joblib
import numpy as np
import pandas as pd

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.detectors.evidgnn import EvidGraphConfig, evidence_pairs
from fraudsim.detectors.external import GnnDetector
from fraudsim.experiments import evidgnn as eg
from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _merge, make_stream, run_grid
from fraudsim.experiments.tuning import load_tuned
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage

OUT = ROOT / "results"
D = "results/anchor"
SCEN = eg.SCEN
TRAIN_SCEN = eg.TRAIN_SCEN
HOLDOUT = tuple(range(201, 206))
DEV = tuple(range(5001, 5006))
K = 5
QUANTILE = 0.995
ANCHOR_STATS = ("anch_mean_p", "anch_frac")
BLOCKS = {"T1": (SCEN, tuple(range(5101, 5121)), {}),
          "T2": (SCEN, tuple(range(5201, 5211)), {"simulation.amount_median": 2000}),
          "T3": (SCEN, tuple(range(5301, 5311)), {"simulation.amount_median": 5000})}
HUB_T4 = {500: tuple(range(5401, 5406)), 2000: tuple(range(5411, 5416))}


def _gnn(engine) -> GnnDetector | None:
    return next((d for d in engine.detectors if isinstance(d, GnnDetector) and d.enabled), None)


def guard_stat(det: GnnDetector | None) -> float | None:
    hist = getattr(det, "flag_history", None) if det is not None else None
    if not hist:
        return None
    return float(median(hist[-K:]))


class AnchorStage(ScoringStage):
    """19 ring features + GNN member statistics + evidence anchoring + guard flag (last column)."""

    tau: float | None = None  # guard threshold; None = guard off

    def featurize(self, engine, ring, others, now_t, since_t):
        feats, view, joined = super().featurize(engine, ring, others, now_t, since_t)
        det = _gnn(engine)
        scores = getattr(det, "last_scores", {}) if det is not None else {}
        thr = det.cfg.node_threshold if det is not None else 0.5
        members = sorted(ring.members)
        ps = [scores.get(m, 0.0) for m in members]
        pairs = evidence_pairs(view, EvidGraphConfig())
        anchored = {x for (u, v) in pairs if u in ring.members and v in ring.members for x in (u, v)}
        a = [p if m in anchored else 0.0 for m, p in zip(members, ps, strict=True)]
        extra = [float(np.mean(ps)), float(np.min(ps)), float(np.mean([p >= thr for p in ps])),
                 float(np.mean(a)), len(anchored) / len(members)] if members else [0.0] * 5
        g = guard_stat(det)
        flag = 1.0 if (self.tau is not None and g is not None and g > self.tau) else 0.0
        return eg._Feats(feats, extra + [flag]), view, joined


class GuardedScorer:
    """Fused scorer while the guard is off; the shipped scorer, mapped to the fused scale, while on."""

    model_type = "anchor_guarded"

    def __init__(self, fused, shipped: RingScorer, n_fused: int, theta_f: float, theta_s: float) -> None:
        self.fused, self.shipped, self.n_fused = fused, shipped, n_fused
        self.theta_f, self.theta_s = theta_f, theta_s
        self.meta = eg._Meta({"guarded": True})
        self.fallbacks = 0

    @property
    def fitted(self) -> bool:
        return True

    def _map(self, r: float) -> float:
        tf, ts = self.theta_f, self.theta_s
        return tf * r / ts if r < ts else tf + (1 - tf) * (r - ts) / (1 - ts)

    def predict(self, x) -> np.ndarray:
        x = np.atleast_2d(np.asarray(x, dtype=float))
        out = []
        for row in x:
            if row[-1] > 0.5:
                self.fallbacks += 1
                out.append(self._map(float(self.shipped.predict(row[:19])[0])))
            else:
                out.append(float(self.fused.predict(row[: self.n_fused])[0]))
        return np.array(out)

    def contributions(self, x) -> dict[str, float]:
        return {}


# ─── Guard reference (label-free statistic on hold-out seeds) ────────────────

def reference() -> dict:
    from fraudsim.experiments.w2_baselines import GNN_MODEL

    vals, per = [], {}
    for sc in TRAIN_SCEN:
        for seed in HOLDOUT:
            stream = make_stream(sc, seed)
            store = InMemoryGraphStore()
            ov = {**{k: {"enabled": False} for k in ("static_cypher", "hub_aware", "temporal_cycle",
                                                      "smurfing", "community")},
                  "gnn": {"model_path": GNN_MODEL, "node_threshold": 0.95, "as_full_detector": True}}
            eng = DetectionEngine(store, build_detectors(store, ov), config=EngineConfig(batch_size=50,
                                                                                         full_interval_s=0.0))
            det = _gnn(eng)
            gs = []
            for batch in eng.batches(stream.events):
                eng.process(batch)
                g = guard_stat(det)
                if g is not None:
                    gs.append(g)
            per[f"{sc}:{seed}"] = {"max": max(gs) if gs else None, "n": len(gs)}
            vals += gs
            print(f"[anchor ref] {sc} {seed}: {len(gs)} batches, max g {max(gs) if gs else None}", flush=True)
    out = {"protocol": "docs/research/anchor_protocol.md", "K": K, "quantile": QUANTILE,
           "tau": float(np.quantile(vals, QUANTILE)), "n_batches": len(vals),
           "q50": float(np.quantile(vals, 0.5)), "q99": float(np.quantile(vals, 0.99)),
           "max": float(max(vals)), "per_stream": per}
    (ROOT / D).mkdir(parents=True, exist_ok=True)
    (ROOT / D / "guard_reference.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "per_stream"}), flush=True)
    return out


def tau() -> float:
    return float(json.loads((ROOT / D / "guard_reference.json").read_text())["tau"])


# ─── Anchored fused scorer ────────────────────────────────────────────────────

def fused_train(node_threshold: float = 0.5) -> None:
    from fraudsim.scoring.train import Row

    rows: list[tuple[Row, list[float]]] = []
    for fold, other in (("A", "B"), ("B", "A")):
        model = f"{eg.D}/graphsage_{other}.pt"
        for sc in TRAIN_SCEN:
            for seed in eg.FOLDS[fold]:
                stream = make_stream(sc, seed)
                store = InMemoryGraphStore()
                stage = AnchorStage(scorer=None, record=True)
                eng = DetectionEngine(store, build_detectors(store, eg.sage_overrides(model, node_threshold)),
                                      tracker=RingTracker(EnsembleConfig()),
                                      config=EngineConfig(batch_size=50, full_interval_s=0.0), scorer=stage)
                eng.run(stream.events)
                gen = stream.generator
                start = gen.ts(0.0).timestamp()
                dur = gen.ts().timestamp() - start
                truth = [{u for _, a, u in r.member_history if a == "join"} for r in gen.ledger.rings.values()]
                for r in stage.rows:
                    best = max((jaccard(set(r["members"]), g) for g in truth), default=0.0)
                    f = r["features"][:-1]  # guard flag is not a scorer input
                    rows.append((Row(sc, seed, f"anchor:{sc}:{seed}", r["ring_id"],
                                     (r["t"] - start) / dur if dur else 0.0, r["status"], int(best >= 0.5),
                                     round(best, 4), f), f))
                print(f"[anchor fused] fold {fold} {sc} {seed}: {len(rows)} rows", flush=True)
    x = np.array([f for _, f in rows], dtype=float)
    y = np.array([r.label for r, _ in rows])
    t = np.array([r.t_frac for r, _ in rows])
    from fraudsim.experiments.evidgnn import FusedScorer as _FS

    s = _FS().fit(x[t < 0.7], y[t < 0.7], x[t >= 0.7], y[t >= 0.7])
    s.meta = {"protocol": "docs/research/anchor_protocol.md", "rows": len(rows), "positives": int(y.sum()),
              "features": "19 ring + gnn_mean_p, gnn_min_p, gnn_frac_flagged, " + ", ".join(ANCHOR_STATS)}
    (ROOT / D).mkdir(parents=True, exist_ok=True)
    joblib.dump(s, ROOT / D / "fused_anchor.joblib")
    pd.DataFrame([{"scenario": r.scenario, "seed": r.seed, "t_frac": r.t_frac, "label": r.label,
                   **{f"f{i}": v for i, v in enumerate(f)}} for r, f in rows]).to_csv(
        ROOT / D / "fused_anchor_rows.csv", index=False)
    print(f"[anchor fused] {len(rows)} rows, {int(y.sum())} positive", flush=True)


# ─── Methods ──────────────────────────────────────────────────────────────────

def method(node_threshold: float, alert: float, variant: str = "anchor", name: str | None = None) -> Method:
    """variant: anchor (anchoring + guard), anchor_only (no guard), guard_only (SagePipe scorer + guard)."""
    from fraudsim.experiments.w2_baselines import GNN_MODEL

    m = Method(name or f"{variant}_{node_threshold}_a{alert}", f"AnchorPipe ({variant})",
               eg.sage_overrides(GNN_MODEL, node_threshold), engine={"full_interval_s": 0.0},
               family="anchor", alert_threshold=alert,
               model_path=f"{D}/fused_anchor.joblib" if variant != "guard_only" else f"{eg.D}/fused_sage.joblib")
    m.ensemble = {}
    m.label = variant
    return m


def _scorer_for(m: Method):
    shipped = RingScorer.load(ROOT / "models/ring_scorer_lr.joblib")
    fused = eg.load_fused(ROOT / m.model_path)
    n = 24 if m.label != "guard_only" else 22
    return GuardedScorer(fused, shipped, n, float(m.alert_threshold), float(load_tuned()["alert_threshold"]))


def run(experiment: str, scenarios, seeds, methods: list[Method], **kw) -> None:
    """Anchor variants use AnchorStage + GuardedScorer; everything else as in the EvidGNN runner."""
    from fraudsim.detectors import evidgnn as det
    from fraudsim.experiments import harness
    from fraudsim.experiments.w2_baselines import skip_explanations

    skip_explanations()
    anchors = [m for m in methods if m.family == "anchor"]
    others = [m for m in methods if m.family != "anchor"]
    if others:
        eg.run_methods(experiment, scenarios, seeds, others, **kw)
    if not anchors:
        return
    t = tau()
    orig_stage, orig_load, orig_stream = harness.ScoringStage, harness.RingScorer.load, harness.make_stream

    for m in anchors:
        guard = m.label != "anchor_only"

        class _Stage(AnchorStage):
            tau = t if guard else None

        sc = _scorer_for(m)
        harness.ScoringStage = _Stage  # type: ignore[misc]
        harness.RingScorer.load = staticmethod(lambda p, _s=sc: _s if "fused_" in str(p) else orig_load(p))  # type: ignore

        def fresh(*a, **k):
            det.SCORE_CACHE = {}
            return orig_stream(*a, **k)

        harness.make_stream = fresh  # type: ignore[assignment]
        try:
            run_grid(experiment, scenarios, seeds, [m], OUT, **kw)
        finally:
            harness.ScoringStage, harness.RingScorer.load, harness.make_stream = orig_stage, orig_load, orig_stream
            det.SCORE_CACHE = None
        print(f"[anchor] {m.name}: guard fallbacks {sc.fallbacks}", flush=True)


NODE_GRID, ALERT_GRID = eg.NODE_GRID, eg.ALERT_GRID
SEL = ROOT / D / "selected.json"


def tune() -> None:
    ms = [method(v, a) for v in NODE_GRID for a in ALERT_GRID]
    run("anchor_tuning/anchor", SCEN, eg.VAL_SEEDS, ms)


def select() -> dict:
    df = pd.read_csv(OUT / "anchor_tuning/anchor/results.csv")
    best, f1 = eg._best(df)
    v, a = eg._thr(best)
    out = {"protocol": "docs/research/anchor_protocol.md", "anchor": {"method": best, "val_f1": f1,
                                                                      "node_threshold": v, "alert": a},
           "tau": tau(), "others": "results/evidgnn_tuning/selected.json"}
    SEL.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def systems(names: list[str]) -> list[Method]:
    s = json.loads(SEL.read_text())["anchor"]
    v, a = s["node_threshold"], s["alert"]
    sel = json.loads(eg.SELECTED.read_text())
    out = []
    for n in names:
        if n in ("anchor", "anchor_only", "guard_only"):
            out.append(method(v, a, n, name=n))
        elif n == "guard_only_sage":  # guard on SagePipe's own selection
            sv, sa = eg._sel_threshold(sel, "sagepipe")
            out.append(method(sv, sa, "guard_only", name=n))
        else:
            out += eg.systems(sel, [n])
    return out


ALL = ["anchor", "anchor_only", "guard_only", "sagepipe", "gnn_unscored", "proposed", "rules", "hybrid"]


def dev() -> None:
    """Development shifts (guard check only): amount median 1,000 and a 300-account hub."""
    from fraudsim.experiments.large_hubs import overrides as hub_ov

    ms = systems(["anchor", "anchor_only", "sagepipe", "proposed"])
    run("anchor_dev/amount1000", SCEN, DEV, ms, scenario_overrides={"simulation.amount_median": 1000})
    run("anchor_dev/hub300", ["hub_heavy"], DEV, ms, scenario_overrides=hub_ov(300),
        extra_columns={"hub_size": 300})


def test(block: str, names: list[str] = ALL) -> None:
    from fraudsim.experiments.large_hubs import overrides as hub_ov

    ms = systems(names)
    if block == "T4":
        for size, seeds in HUB_T4.items():
            for m in ms:
                run(f"anchor_T4/{m.name}", ["hub_heavy"], seeds, [m], scenario_overrides=hub_ov(size),
                    extra_columns={"hub_size": size})
        return
    scen, seeds, ov = BLOCKS[block]
    kw: dict[str, Any] = {"scenario_overrides": ov} if ov else {}
    for m in ms:
        run(f"anchor_{block}/{m.name}", scen, seeds, [m], **kw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--methods", default=",".join(ALL))
    a = ap.parse_args()
    if a.step == "reference":
        reference()
    elif a.step == "fused-train":
        fused_train()
    elif a.step == "tune":
        tune()
    elif a.step == "select":
        select()
    elif a.step == "dev":
        dev()
    elif a.step == "test":
        test(a.arg, a.methods.split(","))


if __name__ == "__main__":
    main()
