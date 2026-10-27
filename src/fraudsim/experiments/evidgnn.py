"""
EvidGNN experiments (docs/research/evidgnn_protocol.md).

    python -m fraudsim.experiments.evidgnn train [--gate 1] [--fold all|A|B] [--tag evidgnn]
    python -m fraudsim.experiments.evidgnn fused-train       # fused ring scorer (OOF GNN scores)
    python -m fraudsim.experiments.evidgnn tune <method>      # validation 301-303, 311-320
    python -m fraudsim.experiments.evidgnn select
    python -m fraudsim.experiments.evidgnn test <block>       # main 4001-4020 / ablation 4101-4120

Systems:
- `evidgnn`: EvidGNN alone (evidence ring rule), no ring scorer.
- `evidpipe`: the pipeline's detectors + EvidGNN detector in one ensemble, scored by a fused ring
  scorer (19 ring features + member GNN statistics, trained with out-of-fold GNN scores).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.detectors.evidgnn import N_FEAT, REL, EvidGnnDetector, EvidGraphConfig, build_graph, make_evid
from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _merge, make_stream, run_grid
from fraudsim.experiments.tuning import load_tuned
from fraudsim.graph.store import InMemoryGraphStore, event_t
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.stage import ScoringStage

OUT = ROOT / "results"
D = "results/evidgnn"
SCEN = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
TRAIN_SCEN = (*SCEN, "scale_sweep")
TRAIN_SEEDS = tuple(range(101, 111))
FOLDS = {"A": tuple(range(101, 106)), "B": tuple(range(106, 111)), "all": TRAIN_SEEDS}
VAL_SEEDS = (301, 302, 303, *range(311, 321))
ALERT_GRID = (0.3, 0.5, 0.7, 0.8, 0.9)
NODE_GRID = (0.5, 0.7, 0.8, 0.9, 0.95)
GNN_STATS = ("gnn_mean_p", "gnn_min_p", "gnn_frac_flagged")


# ─── GNN training ─────────────────────────────────────────────────────────────

def snapshots(scenario: str, seed: int, gcfg: EvidGraphConfig, every_s: float = 5.0):
    from fraudsim.experiments.w2_baselines import _labels_at

    stream = make_stream(scenario, seed)
    store = InMemoryGraphStore()
    eng = DetectionEngine(store, [], config=EngineConfig(batch_size=50))
    out, last = [], None
    for batch in eng.batches(stream.events):
        store.apply(batch)
        now = event_t(batch[-1])
        if last is not None and now - last < every_s:
            continue
        last = now
        view = store.full_view(now - eng.cfg.window_s, now)
        users, x, edges, _ = build_graph(view, store.joined(set(view.users)), gcfg)
        if not users:
            continue
        pos = _labels_at(stream.generator.ledger, now)
        y = np.array([1.0 if u in pos else 0.0 for u in users], dtype=np.float32)
        out.append((x, edges, y, len(users)))
    return out


def train(gate: bool = True, fold: str = "all", tag: str = "evidgnn", epochs: int = 40,
          scenarios: tuple[str, ...] = TRAIN_SCEN) -> Path:
    import torch

    torch.manual_seed(0)
    np.random.seed(0)
    gcfg = EvidGraphConfig(gate=gate)
    t0 = time.perf_counter()
    graphs = []
    for sc in scenarios:
        for seed in FOLDS[fold]:
            graphs += snapshots(sc, seed, gcfg)
        print(f"[evidgnn train {tag}/{fold}] {sc}: {len(graphs)} snapshots", flush=True)
    xs = np.concatenate([g[0] for g in graphs])
    mean, std = xs.mean(0), xs.std(0) + 1e-6
    n_pos = sum(float(g[2].sum()) for g in graphs)
    n = sum(g[3] for g in graphs)
    model = make_evid(hidden=64)
    opt = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=5e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor((n - n_pos) / max(n_pos, 1.0)))
    tens = [(torch.from_numpy((x - mean) / std), {r: torch.from_numpy(e[r]) for r in REL},
             torch.from_numpy(y), k) for x, e, y, k in graphs]
    hist = []
    for ep in range(epochs):
        model.train()
        tot = 0.0
        for i in np.random.permutation(len(tens)):
            x, e, y, k = tens[i]
            opt.zero_grad()
            loss = loss_fn(model(x, e)[:k], y)
            loss.backward()
            opt.step()
            tot += float(loss)
        hist.append(round(tot / len(tens), 4))
    path = ROOT / D / f"{tag}_{fold}.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hparams": {"hidden": 64, "dropout": 0.2},
                "mean": mean.astype(np.float32), "std": std.astype(np.float32)}, path)
    path.with_suffix(".json").write_text(json.dumps({
        "protocol": "docs/research/evidgnn_protocol.md", "gate": gate, "fold": fold,
        "seeds": FOLDS[fold], "scenarios": scenarios, "snapshots": len(graphs), "user_rows": int(n),
        "positive_rows": int(n_pos), "epochs": epochs, "loss_by_epoch": hist, "n_features": N_FEAT,
        "wall_s": round(time.perf_counter() - t0, 1), "torch": torch.__version__}, indent=1))
    print(f"[evidgnn train {tag}/{fold}] done in {time.perf_counter() - t0:.0f}s", flush=True)
    return path


# ─── Fused ring scorer ────────────────────────────────────────────────────────

class FusedScorer:
    """Logistic regression + isotonic calibration over 19 ring features + GNN member statistics."""

    model_type = "fused_logistic_regression"

    def __init__(self) -> None:
        from sklearn.isotonic import IsotonicRegression
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        self.model = Pipeline([("scale", StandardScaler()),
                               ("lr", LogisticRegression(max_iter=2000, class_weight="balanced"))])
        self.calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        self.meta: dict[str, Any] = {}
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, xf, yf, xc, yc) -> FusedScorer:
        self.model.fit(xf, yf)
        self.calibrator.fit(self.model.predict_proba(xc)[:, 1], yc)
        self._fitted = True
        return self

    def raw_proba(self, x) -> np.ndarray:
        x = np.atleast_2d(np.asarray(x, dtype=float))
        return self.model.predict_proba(x)[:, 1]

    def predict(self, x) -> np.ndarray:
        return self.calibrator.predict(self.raw_proba(x))

    def contributions(self, x) -> dict[str, float]:
        return {}


class _Feats:
    """Proxy: the 19 ring features plus GNN member statistics."""

    def __init__(self, base: Any, extra: list[float]) -> None:
        self._b, self._e = base, extra

    def __getattr__(self, name: str) -> Any:
        return getattr(self._b, name)

    def to_vector(self) -> list[float]:
        return list(self._b.to_vector()) + list(self._e)

    def to_dict(self) -> dict[str, float]:
        return self._b.to_dict() | dict(zip(GNN_STATS, self._e, strict=True))


class FusedStage(ScoringStage):
    """Scoring stage that appends GNN member statistics from the engine's EvidGNN detector."""

    def featurize(self, engine, ring, others, now_t, since_t):
        feats, view, joined = super().featurize(engine, ring, others, now_t, since_t)
        det = next((d for d in engine.detectors if isinstance(d, EvidGnnDetector) and d.enabled), None)
        scores = det.last_scores if det is not None else {}
        thr = det.cfg.node_threshold if det is not None else 0.5
        ps = [scores.get(m, 0.0) for m in ring.members]
        extra = [float(np.mean(ps)), float(np.min(ps)), float(np.mean([p >= thr for p in ps]))] if ps else [0.0] * 3
        return _Feats(feats, extra), view, joined


def evidpipe_overrides(model: str, node_threshold: float) -> dict:
    t = load_tuned()
    return _merge(PROPOSED, {"hub_aware": {"edge_threshold": float(t["edge_threshold"])},
                             "evidgnn": {"model_path": model, "node_threshold": node_threshold,
                                         "as_full_detector": True}})


def fused_train(node_threshold: float = 0.5, tag: str = "evidgnn") -> None:
    """Rows from the training seeds; each fold scored by the GNN trained on the other fold."""
    from fraudsim.scoring.train import Row

    rows: list[tuple[Row, list[float]]] = []
    for fold, other in (("A", "B"), ("B", "A")):
        model = f"{D}/{tag}_{other}.pt"
        for sc in TRAIN_SCEN:
            for seed in FOLDS[fold]:
                stream = make_stream(sc, seed)
                store = InMemoryGraphStore()
                stage = FusedStage(scorer=None, record=True)
                eng = DetectionEngine(store, build_detectors(store, evidpipe_overrides(model, node_threshold)),
                                      tracker=RingTracker(EnsembleConfig()),
                                      config=EngineConfig(batch_size=50, full_interval_s=0.0), scorer=stage)
                eng.run(stream.events)
                gen = stream.generator
                start = gen.ts(0.0).timestamp()
                dur = gen.ts().timestamp() - start
                truth = [{u for _, a, u in r.member_history if a == "join"} for r in gen.ledger.rings.values()]
                for r in stage.rows:
                    best = max((jaccard(set(r["members"]), g) for g in truth), default=0.0)
                    rows.append((Row(sc, seed, f"fused:{sc}:{seed}", r["ring_id"],
                                     (r["t"] - start) / dur if dur else 0.0, r["status"], int(best >= 0.5),
                                     round(best, 4), r["features"]), r["features"]))
                print(f"[fused-train] fold {fold} {sc} {seed}: {len(rows)} rows", flush=True)
    x = np.array([f for _, f in rows], dtype=float)
    y = np.array([r.label for r, _ in rows])
    t = np.array([r.t_frac for r, _ in rows])
    s = FusedScorer().fit(x[t < 0.7], y[t < 0.7], x[t >= 0.7], y[t >= 0.7])
    s.meta = {"protocol": "docs/research/evidgnn_protocol.md", "rows": len(rows), "positives": int(y.sum()),
              "features": "19 ring features + " + ", ".join(GNN_STATS), "oof": "fold A scored by GNN B, and vice versa",
              "node_threshold_during_training": node_threshold}
    (ROOT / D).mkdir(parents=True, exist_ok=True)
    joblib.dump(s, ROOT / D / f"fused_{tag}.joblib")
    pd.DataFrame([{"scenario": r.scenario, "seed": r.seed, "t_frac": r.t_frac, "label": r.label,
                   **{f"f{i}": v for i, v in enumerate(f)}} for r, f in rows]).to_csv(ROOT / D / f"fused_{tag}_rows.csv", index=False)
    print(f"[fused-train] {len(rows)} rows, {int(y.sum())} positive", flush=True)


# ─── Methods, tuning, test ────────────────────────────────────────────────────

def method(kind: str, node_threshold: float, alert: float | None = None, tag: str = "evidgnn",
           ring_rule: str = "evidence", gate: bool = True, name: str | None = None) -> Method:
    model = f"{D}/{tag}_all.pt"
    if kind == "evidgnn":
        from fraudsim.experiments.w2_baselines import OFF

        ov = {**OFF, "evidgnn": {"model_path": model, "node_threshold": node_threshold,
                                 "ring_rule": ring_rule, "gate": gate}}
        return Method(name or f"evidgnn_{node_threshold}", "EvidGNN", ov, engine={"incremental": False},
                      scored=False, family="evidgnn")
    if kind == "evidpipe":
        m = Method(name or f"evidpipe_{node_threshold}_a{alert}", "EvidGNN pipeline",
                   evidpipe_overrides(model, node_threshold), engine={"full_interval_s": 0.0},
                   family="evidgnn", alert_threshold=alert, model_path=f"{D}/fused_{tag}.joblib")
        m.ensemble = {}
        return m
    raise ValueError(kind)


def run_methods(experiment: str, scenarios, seeds, methods: list[Method]) -> None:
    """Like run_grid, but EvidPipe methods use the FusedStage and the fused scorer."""
    from fraudsim.experiments import harness

    fused = [m for m in methods if m.family == "evidgnn" and m.model_path and "fused" in m.model_path]
    plain = [m for m in methods if m not in fused]
    if plain:
        run_grid(experiment, scenarios, seeds, plain, OUT)
    if fused:
        orig_stage, orig_load = harness.ScoringStage, harness.RingScorer.load
        harness.ScoringStage = FusedStage  # type: ignore[misc]
        harness.RingScorer.load = staticmethod(lambda p: joblib.load(p))  # type: ignore[method-assign]
        try:
            run_grid(experiment, scenarios, seeds, fused, OUT)
        finally:
            harness.ScoringStage = orig_stage  # type: ignore[misc]
            harness.RingScorer.load = orig_load  # type: ignore[method-assign]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--gate", type=int, default=1)
    ap.add_argument("--fold", default="all")
    ap.add_argument("--tag", default="evidgnn")
    a = ap.parse_args()
    if a.step == "train":
        train(bool(a.gate), a.fold, a.tag)
    elif a.step == "fused-train":
        fused_train(tag=a.tag)


if __name__ == "__main__":
    main()
