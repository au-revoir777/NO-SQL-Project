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
VAL_SEEDS = (301, 302, 303)  # protocol S2: 311-320 stays reserved and unused
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


CACHE = ROOT / ".cache" / "evidgnn"


def cached_snapshots(scenario: str, seed: int, gcfg: EvidGraphConfig) -> list:
    """Snapshots per stream, cached on disk (not part of results) so restarts and folds reuse them."""
    p = CACHE / f"{'gate' if gcfg.gate else 'nogate'}_{scenario}_{seed}.joblib"
    if p.exists():
        return joblib.load(p)
    out = snapshots(scenario, seed, gcfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(out, p)
    return out


def train(gate: bool = True, fold: str = "all", tag: str = "evidgnn", epochs: int = 40,
          scenarios: tuple[str, ...] = TRAIN_SCEN) -> Path:
    """Identical settings to the GraphSAGE baseline. Checkpoints every epoch and resumes, so a
    stopped run continues from where it was; the result equals an uninterrupted run except for
    the RNG state, which is saved and restored with the checkpoint."""
    import torch

    torch.set_num_threads(1)  # protocol amendment 1: 2-thread runs were ~250x slower (oversubscription)
    torch.manual_seed(0)
    np.random.seed(0)
    gcfg = EvidGraphConfig(gate=gate)
    t0 = time.perf_counter()
    graphs = []
    for sc in scenarios:
        for seed in FOLDS[fold]:
            graphs += cached_snapshots(sc, seed, gcfg)
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
    hist: list[float] = []
    ckpt = CACHE / f"ckpt_{tag}_{fold}.pt"
    if ckpt.exists():
        st = torch.load(ckpt, weights_only=False)
        model.load_state_dict(st["model"])
        opt.load_state_dict(st["opt"])
        hist = st["hist"]
        torch.set_rng_state(st["torch_rng"])
        np.random.set_state(st["np_rng"])
        print(f"[evidgnn train {tag}/{fold}] resumed at epoch {len(hist)}", flush=True)
    for ep in range(len(hist), epochs):
        te = time.perf_counter()
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
        CACHE.mkdir(parents=True, exist_ok=True)
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "hist": hist,
                    "torch_rng": torch.get_rng_state(), "np_rng": np.random.get_state()}, ckpt)
        print(f"[evidgnn train {tag}/{fold}] epoch {ep + 1}/{epochs} loss {hist[-1]} "
              f"({time.perf_counter() - te:.0f}s)", flush=True)
    path = ROOT / D / f"{tag}_{fold}.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "hparams": {"hidden": 64, "dropout": 0.2},
                "mean": mean.astype(np.float32), "std": std.astype(np.float32)}, path)
    path.with_suffix(".json").write_text(json.dumps({
        "protocol": "docs/research/evidgnn_protocol.md", "gate": gate, "fold": fold,
        "seeds": FOLDS[fold], "scenarios": scenarios, "snapshots": len(graphs), "user_rows": int(n),
        "positive_rows": int(n_pos), "epochs": epochs, "loss_by_epoch": hist, "n_features": N_FEAT,
        "wall_s_last_session": round(time.perf_counter() - t0, 1), "torch": torch.__version__}, indent=1))
    print(f"[evidgnn train {tag}/{fold}] done in {time.perf_counter() - t0:.0f}s", flush=True)
    return path


# ─── Fused ring scorer ────────────────────────────────────────────────────────

class _Meta(dict):
    """Training metadata; `reliability` is empty (explanations then omit the observed rate)."""

    reliability: list = []


def load_fused(path) -> "FusedScorer":
    s = joblib.load(path)
    if not isinstance(s.meta, _Meta):
        s.meta = _Meta(s.meta)
    return s


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
    # instantiate through the package path so the pickle loads outside `python -m` (__main__)
    from fraudsim.experiments.evidgnn import FusedScorer as _FS

    s = _FS().fit(x[t < 0.7], y[t < 0.7], x[t >= 0.7], y[t >= 0.7])
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
    """Like run_grid, but EvidPipe methods use the FusedStage and the fused scorer.
    GNN node scores are cached per stream (they do not depend on any threshold)."""
    from fraudsim.detectors import evidgnn as det
    from fraudsim.experiments import harness

    orig_stream = harness.make_stream

    def fresh_stream(*a, **k):
        det.SCORE_CACHE = {}
        return orig_stream(*a, **k)

    harness.make_stream = fresh_stream  # type: ignore[assignment]
    try:
        _run_methods(experiment, scenarios, seeds, methods)
    finally:
        harness.make_stream = orig_stream  # type: ignore[assignment]
        det.SCORE_CACHE = None


def _run_methods(experiment: str, scenarios, seeds, methods: list[Method]) -> None:
    from fraudsim.experiments import harness
    from fraudsim.experiments.w2_baselines import skip_explanations

    # Counterfactual explanations assume the 19 shipped features; they never change alerts or
    # metrics (risk is computed first), so they are skipped for every method, as in W2/W3.
    skip_explanations()

    fused = [m for m in methods if m.family == "evidgnn" and m.model_path and "fused" in m.model_path]
    plain = [m for m in methods if m not in fused]
    if plain:
        run_grid(experiment, scenarios, seeds, plain, OUT)
    if fused:
        orig_stage, orig_load = harness.ScoringStage, harness.RingScorer.load
        harness.ScoringStage = FusedStage  # type: ignore[misc]
        harness.RingScorer.load = staticmethod(  # type: ignore[method-assign]
            lambda p: load_fused(p) if "fused_" in str(p) else orig_load(p))
        try:
            run_grid(experiment, scenarios, seeds, fused, OUT)
        finally:
            harness.ScoringStage = orig_stage  # type: ignore[misc]
            harness.RingScorer.load = orig_load  # type: ignore[method-assign]


# ─── Tuning (validation 301-303) and selection ────────────────────────────────

GNN_WIDE = (0.97, 0.98, 0.99, 0.995)  # S0C fairness fix for the GraphSAGE baseline
TUNE = "evidgnn_tuning"
SELECTED = OUT / TUNE / "selected.json"


def gnn_method(threshold: float, ring_rule: str = "any", name: str | None = None) -> Method:
    from fraudsim.experiments.w2_baselines import make

    m = make("gnn", threshold, None, scored=False)
    if ring_rule != "any":
        m.overrides["gnn"]["ring_rule"] = ring_rule
    if name:
        m.name = m.label = name
    return m


def tune(what: str) -> None:
    if what == "gnn-wide":
        run_grid(f"{TUNE}/gnn_wide", SCEN, VAL_SEEDS, [gnn_method(v) for v in GNN_WIDE], OUT)
    elif what == "evidgnn":  # A0 and A2 (same scores, two ring rules)
        ms = [method("evidgnn", v) for v in NODE_GRID]
        ms += [method("evidgnn", v, ring_rule="any", name=f"evidgnn_any_{v}") for v in NODE_GRID]
        run_methods(f"{TUNE}/evidgnn", SCEN, VAL_SEEDS, ms)
    elif what == "nogate":  # A1
        ms = [method("evidgnn", v, tag="evidgnn_nogate", gate=False, name=f"evidgnn_nogate_{v}") for v in NODE_GRID]
        run_methods(f"{TUNE}/nogate", SCEN, VAL_SEEDS, ms)
    elif what == "gnn-evidence":  # A3: GraphSAGE with the evidence ring rule
        grid = (0.5, 0.7, 0.8, 0.9, 0.95, *GNN_WIDE)
        run_grid(f"{TUNE}/gnn_evidence", SCEN, VAL_SEEDS,
                 [gnn_method(v, "evidence", f"gnn_evidence_{v}") for v in grid], OUT)
    elif what == "evidpipe":
        ms = [method("evidpipe", v, a) for v in NODE_GRID for a in ALERT_GRID]
        run_methods(f"{TUNE}/evidpipe", SCEN, VAL_SEEDS, ms)
    else:
        raise ValueError(what)


def _best(df: pd.DataFrame, prefix: str | None = None) -> tuple[str, float]:
    df = df.assign(f1=df["f1"].fillna(0))
    if prefix:
        df = df[df["method"].str.startswith(prefix)]
    f = df.groupby("method")["f1"].mean()
    # ties go to the lower threshold: names sort by threshold within a family
    best = max(sorted(f.index, key=_thr), key=lambda m: round(float(f[m]), 6))
    return best, round(float(f[best]), 4)


def _thr(name: str) -> tuple[float, ...]:
    out = []
    for tok in name.replace("_a", "_").split("_"):
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return tuple(out)


def select() -> dict:
    """Selection on validation F1 only; written before any test-block run."""
    read = lambda d: pd.read_csv(OUT / TUNE / d / "results.csv")  # noqa: E731
    w2 = json.loads((OUT / "w2_tuning/selected.json").read_text())
    w2gnn = pd.read_csv(OUT / "w2_tuning/gnn/results.csv")
    un = pd.concat([w2gnn[w2gnn["method"].str.endswith("_unscored")], read("gnn_wide")])
    out: dict[str, Any] = {"protocol": "docs/research/evidgnn_protocol.md"}
    out["gnn_unscored"] = dict(zip(("method", "val_f1"), _best(un), strict=True))
    out["gnn_scored"] = w2["gnn"]
    out["rules"] = w2["rules"]
    out["hybrid"] = w2["hybrid"]
    ev = read("evidgnn")
    out["evidgnn"] = dict(zip(("method", "val_f1"), _best(ev[~ev["method"].str.startswith("evidgnn_any")]), strict=True))
    out["evidgnn_any"] = dict(zip(("method", "val_f1"), _best(ev, "evidgnn_any"), strict=True))
    for key, d in (("evidgnn_nogate", "nogate"), ("gnn_evidence", "gnn_evidence"), ("evidpipe", "evidpipe")):
        if (OUT / TUNE / d / "results.csv").exists():
            out[key] = dict(zip(("method", "val_f1"), _best(read(d)), strict=True))
    cands = {k: out[k]["val_f1"] for k in ("gnn_unscored", "gnn_scored", "rules")}
    out["strongest_existing"] = max(cands, key=cands.get)
    SELECTED.parent.mkdir(parents=True, exist_ok=True)
    SELECTED.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


# ─── Test blocks ──────────────────────────────────────────────────────────────

MAIN = tuple(range(4001, 4021))
ABL = tuple(range(4101, 4121))


def _sel_threshold(sel: dict, key: str) -> tuple[float, ...]:
    return _thr(sel[key]["method"])


def systems(sel: dict, names: list[str]) -> list[Method]:
    from fraudsim.experiments.w2_baselines import _parse, make, overrides

    out = []
    for n in names:
        if n == "evidpipe":
            v, a = _sel_threshold(sel, "evidpipe")
            out.append(method("evidpipe", v, a, name="evidpipe"))
        elif n == "evidpipe_shipped_scorer":  # A6
            v, _ = _sel_threshold(sel, "evidpipe")
            t = load_tuned()
            m = method("evidpipe", v, float(t["alert_threshold"]), name=n)
            m.model_path = None
            out.append(m)
        elif n == "evidgnn":
            out.append(method("evidgnn", _sel_threshold(sel, "evidgnn")[0], name=n))
        elif n == "evidgnn_any":  # A2
            out.append(method("evidgnn", _sel_threshold(sel, "evidgnn_any")[0], ring_rule="any", name=n))
        elif n == "evidgnn_nogate":  # A1
            out.append(method("evidgnn", _sel_threshold(sel, "evidgnn_nogate")[0], tag="evidgnn_nogate",
                              gate=False, name=n))
        elif n == "gnn_evidence":  # A3
            out.append(gnn_method(_sel_threshold(sel, "gnn_evidence")[0], "evidence", n))
        elif n == "gnn_unscored":  # A4 / existing
            out.append(gnn_method(_sel_threshold(sel, "gnn_unscored")[0], name=n))
        elif n in ("gnn_scored", "rules", "hybrid"):
            mm, v, a, s_ = _parse(sel[n]["method"])
            m = make(mm, v, a, s_)
            m.name = n
            out.append(m)
        elif n == "proposed":
            t = load_tuned()
            ov = _merge(PROPOSED, {"hub_aware": {"edge_threshold": float(t["edge_threshold"])}})
            out.append(Method("proposed", "proposed (shipped)", ov, family="proposed",
                              alert_threshold=float(t["alert_threshold"])))
        else:
            raise ValueError(n)
    _ = overrides
    return out


def test(block: str, names: list[str]) -> None:
    from fraudsim.experiments.w2_baselines import skip_explanations

    skip_explanations()
    sel = json.loads(SELECTED.read_text())
    seeds = {"main": MAIN, "ablation": ABL}[block]
    for m in systems(sel, names):
        run_methods(f"evidgnn_{block}/{m.name}", SCEN, seeds, [m])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--gate", type=int, default=1)
    ap.add_argument("--fold", default="all")
    ap.add_argument("--tag", default="evidgnn")
    ap.add_argument("--methods", default="evidpipe,evidgnn,gnn_unscored,gnn_scored,hybrid,proposed,rules")
    a = ap.parse_args()
    if a.step == "train":
        train(bool(a.gate), a.fold, a.tag)
    elif a.step == "train-loso":  # H3: one model per left-out accuracy scenario
        for left in SCEN:
            if not (ROOT / D / f"evidgnn_loso_{left}_all.pt").exists():
                train(True, "all", f"evidgnn_loso_{left}", scenarios=tuple(x for x in TRAIN_SCEN if x != left))
    elif a.step == "fused-train":
        fused_train(tag=a.tag)
    elif a.step == "tune":
        tune(a.arg)
    elif a.step == "select":
        select()
    elif a.step == "test":
        test(a.arg, a.methods.split(","))


if __name__ == "__main__":
    main()
