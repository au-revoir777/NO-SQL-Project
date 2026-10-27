"""
EvidGNN: evidence-gated message passing for fraud-ring detection (docs/research/evidgnn_protocol.md).

Graph (users only carry labels; attributes are nodes):
- R1 user-attribute links, only for attributes with degree <= busy_degree (27 at theta_e = 0.3):
  a busy attribute never passes a message on its own (the gate);
- R2 user-user transfers in the window;
- R3 user-user evidence edges: pairs with W(u,v) >= theta_e and a non-zero attribute term, where W
  is the pipeline's pairwise evidence (busy attributes count only as support). Each user keeps its
  top-k evidence edges by W (deterministic, evidence-aware neighbour selection).

Candidate pairs for R3 are enumerated from non-busy shared attributes and transfers only, so a pair
linked solely by busy attributes is never formed (a pair sharing two or more busy attributes and
nothing else is missed; the engine's fan-out mode has the same property).

Model: 2-layer relation-aware SAGE (separate mean aggregator per relation, weighted mean by W on R3).
Ring rule ("evidence"): connected components of R3 restricted to flagged users, peeled to density
>= 0.75 and size 3-25 (the pipeline's peel). The baseline GraphSAGE rule ("any") is available too.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fraudsim.detectors.base import BaseDetector, DetectorConfig
from fraudsim.detectors.hubaware import _peel, decay, hub_weight
from fraudsim.graph.store import GraphStore, GraphView
from fraudsim.types import DetectorType, RingCandidate, RingType

ATTR_KINDS = ("device", "card", "ip")
N_FEAT = 16
REL = ("attr", "txn", "evid")


@dataclass(slots=True)
class EvidGraphConfig:
    weight_method: str = "inverse_log_degree"
    edge_threshold: float = 0.3
    busy_degree: int = 27
    half_life_s: float = 300.0
    txn_weight: float = 0.15
    max_txn_weight: float = 0.6
    top_k: int = 16
    gate: bool = True  # False: busy attributes pass messages like any other (ablation A1/A4)


def evidence_pairs(view: GraphView, cfg: EvidGraphConfig) -> dict[tuple[str, str], float]:
    by_user: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)
    by_attr: dict[tuple[str, str], list[str]] = defaultdict(list)
    for lk in view.links:
        a = (lk.kind, lk.attr)
        by_user[lk.user][a] = lk.t
        by_attr[a].append(lk.user)
    deg = {a: view.attr_degree.get(a, len(us)) for a, us in by_attr.items()}
    cand: set[tuple[str, str]] = set()
    for a, us in by_attr.items():
        if deg[a] <= cfg.busy_degree and len(us) >= 2:
            s = sorted(set(us))
            cand.update((s[i], s[j]) for i in range(len(s)) for j in range(i + 1, len(s)))
    txn: dict[tuple[str, str], float] = defaultdict(float)
    for t in view.txns:
        if t.sender != t.receiver:
            k = (min(t.sender, t.receiver), max(t.sender, t.receiver))
            txn[k] += cfg.txn_weight * decay(view.now_t - t.t, cfg.half_life_s)
    cand.update(txn)
    out: dict[tuple[str, str], float] = {}
    for u, v in cand:
        au, av = by_user.get(u, {}), by_user.get(v, {})
        shared = au.keys() & av.keys()
        if not shared:
            continue
        attr = sum(hub_weight(deg.get(a, 2), cfg.weight_method)
                   * decay(view.now_t - min(au[a], av[a]), cfg.half_life_s) for a in shared)
        w = attr + min(txn.get((u, v), 0.0), cfg.max_txn_weight)
        if attr > 0 and w >= cfg.edge_threshold:
            out[(u, v)] = w
    return out


def build_graph(view: GraphView, joined: dict[str, float] | None, cfg: EvidGraphConfig):
    """Node features, relation edge lists (src, dst, weight), and the evidence pairs."""
    users = sorted(view.users)
    uidx = {u: i for i, u in enumerate(users)}
    by_attr: dict[tuple[str, str], list[str]] = defaultdict(list)
    per_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    busy_held: dict[str, int] = defaultdict(int)
    for lk in view.links:
        if lk.user in uidx:
            by_attr[(lk.kind, lk.attr)].append(lk.user)
            per_kind[lk.user][ATTR_KINDS.index(lk.kind) if lk.kind in ATTR_KINDS else 2] += 1
    deg = {a: view.attr_degree.get(a, len(us)) for a, us in by_attr.items()}
    passing = [a for a in by_attr if (deg[a] <= cfg.busy_degree or not cfg.gate)]
    aidx = {a: len(users) + i for i, a in enumerate(sorted(passing))}
    for a, us in by_attr.items():
        if deg[a] > cfg.busy_degree:
            for u in us:
                busy_held[u] += 1
    n = len(users) + len(aidx)
    x = np.zeros((n, N_FEAT), dtype=np.float32)
    rel: dict[str, list] = {r: [[], [], []] for r in REL}
    for a, us in by_attr.items():
        if a not in aidx:
            continue
        for u in us:
            for s_, d_ in ((uidx[u], aidx[a]), (aidx[a], uidx[u])):
                rel["attr"][0].append(s_)
                rel["attr"][1].append(d_)
                rel["attr"][2].append(1.0)
    oc, ic, oa, ia = (defaultdict(float) for _ in range(4))
    for t in view.txns:
        if t.sender in uidx and t.receiver in uidx and t.sender != t.receiver:
            oc[t.sender] += 1
            ic[t.receiver] += 1
            oa[t.sender] += t.amount
            ia[t.receiver] += t.amount
            for s_, d_ in ((uidx[t.sender], uidx[t.receiver]), (uidx[t.receiver], uidx[t.sender])):
                rel["txn"][0].append(s_)
                rel["txn"][1].append(d_)
                rel["txn"][2].append(1.0)
    pairs = evidence_pairs(view, cfg) if cfg.gate else {}
    nbrs: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for (u, v), w in pairs.items():
        nbrs[u].append((w, v))
        nbrs[v].append((w, u))
    for u, lst in nbrs.items():
        for w, v in sorted(lst, key=lambda z: (-z[0], z[1]))[: cfg.top_k]:
            rel["evid"][0].append(uidx[v])
            rel["evid"][1].append(uidx[u])
            rel["evid"][2].append(w)
    for u, i in uidx.items():
        x[i, 0:3] = np.log1p(per_kind[u])
        x[i, 3] = math.log1p(oc[u])
        x[i, 4] = math.log1p(ic[u])
        x[i, 5] = math.log1p(oa[u])
        x[i, 6] = math.log1p(ia[u])
        if joined and u in joined:
            x[i, 7] = math.log1p(max(0.0, view.now_t - joined[u]))
        x[i, 8] = 1.0
        ws = [w for w, _ in nbrs.get(u, [])]
        x[i, 11] = math.log1p(len(ws))
        x[i, 12] = math.log1p(sum(ws))
        x[i, 13] = max(ws) if ws else 0.0
        x[i, 14] = math.log1p(busy_held[u])
    for (kind, aid), i in aidx.items():
        x[i, ATTR_KINDS.index(kind) if kind in ATTR_KINDS else 2] = 1.0
        x[i, 9] = 1.0
        x[i, 10] = math.log1p(deg[(kind, aid)])
    edges = {r: np.array(v, dtype=np.float32) if v[0] else np.zeros((3, 0), dtype=np.float32)
             for r, v in rel.items()}
    return users, x, edges, pairs


def make_evid(hidden: int = 64, dropout: float = 0.2):
    import torch
    from torch import nn

    class EvidSage(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.s1 = nn.Linear(N_FEAT, hidden)
            self.r1 = nn.ModuleDict({r: nn.Linear(N_FEAT, hidden, bias=False) for r in REL})
            self.s2 = nn.Linear(hidden, hidden)
            self.r2 = nn.ModuleDict({r: nn.Linear(hidden, hidden, bias=False) for r in REL})
            self.out = nn.Linear(hidden, 1)
            self.drop = nn.Dropout(dropout)

        @staticmethod
        def agg(h, e, n):
            out = torch.zeros(n, h.shape[1])
            if e.shape[1] == 0:
                return out
            src, dst, w = e[0].long(), e[1].long(), e[2].unsqueeze(1)
            out.index_add_(0, dst, h[src] * w)
            norm = torch.zeros(n).index_add_(0, dst, e[2]).clamp(min=1e-9).unsqueeze(1)
            return out / norm

        def forward(self, x, edges):
            n = x.shape[0]
            h = self.s1(x) + sum(self.r1[r](self.agg(x, edges[r], n)) for r in REL)
            h = self.drop(torch.relu(h))
            h2 = self.s2(h) + sum(self.r2[r](self.agg(h, edges[r], n)) for r in REL)
            return self.out(self.drop(torch.relu(h2))).squeeze(-1)

    return EvidSage()


def evidence_rings(view: GraphView, scores: dict[str, float], flagged: set[str], min_size: int = 3,
                   max_size: int = 25, density: float = 0.75, pairs: dict | None = None):
    """Evidence ring rule: components of evidence edges among flagged users, peeled when large."""
    if pairs is None:
        pairs = evidence_pairs(view, EvidGraphConfig())
    adj: dict[str, dict[str, float]] = defaultdict(dict)
    for (u, v), w in pairs.items():
        if u in flagged and v in flagged:
            adj[u][v] = adj[v][u] = w
    out, seen = [], set()
    for u in sorted(adj):
        if u in seen:
            continue
        comp, stack = set(), [u]
        while stack:
            a = stack.pop()
            if a not in comp:
                comp.add(a)
                stack.extend(set(adj[a]) - comp)
        seen |= comp
        if len(comp) > max_size:
            comp = _peel(adj, comp, density, max_size, min_size) or set()
        if min_size <= len(comp) <= max_size:
            out.append((comp, float(np.mean([scores[m] for m in comp]))))
    return out


# Optional per-stream cache of node scores and evidence pairs. Scores depend only on the graph
# state (events seen so far), the model and the graph settings, never on the node or alert
# threshold, so a tuning grid over thresholds can reuse them. The experiment runner sets this to
# {} and clears it whenever a new stream starts; None (default) disables caching.
SCORE_CACHE: dict | None = None


@dataclass(slots=True)
class EvidGnnConfig(DetectorConfig):
    detector_type: DetectorType = DetectorType.COMMUNITY
    name: str = "EvidGNN"
    model_path: str = "results/evidgnn/evidgnn.pt"
    node_threshold: float = 0.5
    ring_rule: str = "evidence"  # or "any" (the GraphSAGE baseline's rule)
    gate: bool = True
    top_k: int = 16
    as_full_detector: bool = False
    min_ring_size: int = 3
    max_ring_size: int = 25
    min_edge_density: float = 0.75
    extra: dict[str, Any] = field(default_factory=dict)


class EvidGnnDetector(BaseDetector):
    incremental = True

    def __init__(self, config: EvidGnnConfig | None = None, store: GraphStore | None = None):
        super().__init__(config or EvidGnnConfig(), store)
        self.cfg: EvidGnnConfig = self._config  # type: ignore[assignment]
        self._model = None
        self.last_scores: dict[str, float] = {}
        if self.cfg.as_full_detector:
            self.incremental = False

    def graph_cfg(self) -> EvidGraphConfig:
        return EvidGraphConfig(gate=self.cfg.gate, top_k=self.cfg.top_k)

    def _load(self):
        if self._model is None:
            import torch

            from fraudsim.experiments.harness import ROOT

            st = torch.load(ROOT / self.cfg.model_path, weights_only=False)
            m = make_evid(**st["hparams"])
            m.load_state_dict(st["state_dict"])
            m.eval()
            self._model = (m, st["mean"], st["std"])
        return self._model

    def node_scores(self, view: GraphView) -> tuple[dict[str, float], dict]:
        key = None
        if SCORE_CACHE is not None:
            key = (self.cfg.model_path, self.cfg.gate, self.cfg.top_k, view.now_t, view.since_t,
                   len(view.users), len(view.links), len(view.txns))
            if key in SCORE_CACHE:
                return SCORE_CACHE[key]
        out = self._node_scores(view)
        if key is not None:
            SCORE_CACHE[key] = out
        return out

    def _node_scores(self, view: GraphView) -> tuple[dict[str, float], dict]:
        import torch

        model, mean, std = self._load()
        joined = self.store.joined(set(view.users)) if self.store is not None else None
        users, x, edges, pairs = build_graph(view, joined, self.graph_cfg())
        if not users:
            return {}, pairs
        with torch.no_grad():
            p = torch.sigmoid(model(torch.from_numpy((x - mean) / std),
                                    {r: torch.from_numpy(e) for r, e in edges.items()})).numpy()
        return {u: float(p[i]) for i, u in enumerate(users)}, pairs

    def detect(self, view: GraphView) -> list[RingCandidate]:
        cfg = self.cfg
        scores, pairs = self.node_scores(view)
        self.last_scores = scores
        flagged = {u for u, p in scores.items() if p >= cfg.node_threshold}
        if len(flagged) < cfg.min_ring_size:
            return []
        adj: dict[str, dict[str, float]] = defaultdict(dict)
        if cfg.ring_rule == "evidence":
            if not pairs:
                pairs = evidence_pairs(view, self.graph_cfg())
            for (u, v), w in pairs.items():
                if u in flagged and v in flagged:
                    adj[u][v] = w
                    adj[v][u] = w
        else:
            for links in view.links_by_attr().values():
                us = sorted({lk.user for lk in links} & flagged)
                for i, u in enumerate(us):
                    for v in us[i + 1:]:
                        adj[u][v] = adj[v][u] = 1.0
            for t in view.txns:
                if t.sender in flagged and t.receiver in flagged and t.sender != t.receiver:
                    adj[t.sender][t.receiver] = adj[t.receiver][t.sender] = 1.0
        out, seen = [], set()
        for u in sorted(adj):
            if u in seen:
                continue
            comp, stack = set(), [u]
            while stack:
                a = stack.pop()
                if a not in comp:
                    comp.add(a)
                    stack.extend(set(adj[a]) - comp)
            seen |= comp
            if cfg.ring_rule == "evidence" and len(comp) > cfg.max_ring_size:
                comp = _peel(adj, comp, cfg.min_edge_density, cfg.max_ring_size, cfg.min_ring_size) or set()
            if cfg.min_ring_size <= len(comp) <= cfg.max_ring_size:
                risk = float(np.mean([scores[m] for m in comp]))
                out.append(self._candidate(RingType.MIXED_ATTRIBUTE, comp, view, risk,
                                           {"algorithm": "evidgnn", "rule": cfg.ring_rule,
                                            "mean_node_p": round(risk, 4)}))
        return out
