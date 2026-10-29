"""
External baselines for W2 (docs/research/w2_protocol.md). Each one emits ring candidates
of 3-25 users, which go through the same tracker (two-hit confirmation) and, when scored,
through a scorer trained on that method's own candidates.

- PeelingDetector: FRAUDAR-style greedy peeling (Hooi et al., KDD 2016) on the bipartite
  graph of users x objects, where objects are shared attributes and money partners; edges
  weighted by FRAUDAR's column weight 1/log(deg + 5). Blocks are extracted one after
  another (each found block's users are removed). Spade (Jiang et al., PVLDB 2022) maintains
  the same peeling incrementally and reports the identical peeling sequence, so recomputing
  it on the full graph after every batch gives Spade's output (not its latency).
- LeidenDetector: Leiden communities (Traag et al., 2019; leidenalg) on the same user-user
  projection as the Louvain baseline, with the Louvain baseline's size and density filter.
- GnnDetector: a GraphSAGE node classifier (mean aggregator, 2 layers) on the heterogeneous
  user-attribute-transfer graph, trained on ring membership labels; flagged users are grouped
  into rings by a fixed rule (connected components over shared attributes and transfers among
  flagged users, size 3-25).

All three run on the whole graph (set engine incremental=False for the method).
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from fraudsim.detectors.base import BaseDetector, DetectorConfig
from fraudsim.graph.store import GraphStore, GraphView
from fraudsim.types import DetectorType, RingCandidate, RingType

# ─── FRAUDAR-style peeling ────────────────────────────────────────────────────


@dataclass(slots=True)
class PeelingConfig(DetectorConfig):
    detector_type: DetectorType = DetectorType.COMMUNITY
    name: str = "FraudarPeeling"
    min_block_score: float = 0.5  # tuned: minimum g(S) = f(S)/|S| of an accepted block
    max_blocks: int = 10
    min_ring_size: int = 3
    max_ring_size: int = 25
    column_c: float = 5.0  # FRAUDAR's c in 1/log(x + c)
    use_transfers: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


def _bipartite(view: GraphView, use_transfers: bool) -> dict[str, dict[str, None]]:
    """user -> set of objects (attributes, and money partners as 'rcv:'/'snd:' objects)."""
    rows: dict[str, dict[str, None]] = defaultdict(dict)
    for attr, links in view.links_by_attr().items():
        for lk in links:
            rows[lk.user][f"{attr[0]}:{attr[1]}"] = None
    if use_transfers:
        for t in view.txns:
            if t.sender != t.receiver:
                rows[t.sender][f"rcv:{t.receiver}"] = None
                rows[t.receiver][f"snd:{t.sender}"] = None
    return rows


def peel_once(rows: dict[str, dict[str, None]], c: float) -> tuple[set[str], set[str], float]:
    """One FRAUDAR greedy pass. Returns (users, objects, best g)."""
    cols: dict[str, set[str]] = defaultdict(set)
    for u, objs in rows.items():
        for o in objs:
            cols[o].add(u)
    w = {o: 1.0 / math.log(len(us) + c) for o, us in cols.items()}
    nodes: dict[str, float] = {}
    for u, objs in rows.items():
        nodes[("u", u)] = sum(w[o] for o in objs)  # type: ignore[index]
    for o, us in cols.items():
        nodes[("o", o)] = w[o] * len(us)  # type: ignore[index]
    total = sum(v for k, v in nodes.items() if k[0] == "u")  # type: ignore[index]
    alive = set(nodes)
    heap = [(v, k) for k, v in nodes.items()]
    heapq.heapify(heap)
    best_g, best_size, order = total / max(len(alive), 1), len(alive), []
    while len(alive) > 1:
        v, k = heapq.heappop(heap)
        if k not in alive or abs(nodes[k] - v) > 1e-12:
            continue
        alive.discard(k)
        order.append(k)
        total -= nodes[k]
        kind, name = k
        neigh = (("o", o) for o in rows[name]) if kind == "u" else (("u", u) for u in cols[name])
        for nb in neigh:
            if nb in alive:
                ew = w[name] if kind == "o" else w[nb[1]]
                nodes[nb] -= ew
                heapq.heappush(heap, (nodes[nb], nb))
        g = total / len(alive)
        if g > best_g + 1e-12:
            best_g, best_size = g, len(alive)
    removed = set(order[: len(nodes) - best_size])
    keep = set(nodes) - removed
    return ({n for t, n in keep if t == "u"}, {n for t, n in keep if t == "o"}, best_g)


class PeelingDetector(BaseDetector):
    incremental = True  # run on the full view each batch (engine incremental=False)

    def __init__(self, config: PeelingConfig | None = None, store: GraphStore | None = None):
        super().__init__(config or PeelingConfig(), store)
        self.cfg: PeelingConfig = self._config  # type: ignore[assignment]

    def detect(self, view: GraphView) -> list[RingCandidate]:
        cfg = self.cfg
        rows = _bipartite(view, cfg.use_transfers)
        out: list[RingCandidate] = []
        for _ in range(cfg.max_blocks):
            rows = {u: o for u, o in rows.items() if o}
            if len(rows) < cfg.min_ring_size:
                break
            users, objs, g = peel_once(rows, cfg.column_c)
            if not users or g < cfg.min_block_score:
                break
            if cfg.min_ring_size <= len(users) <= cfg.max_ring_size:
                out.append(self._candidate(RingType.MIXED_ATTRIBUTE, users, view, min(1.0, g),
                                           {"algorithm": "fraudar_peeling", "g": round(g, 4),
                                            "objects": len(objs)}))
            for u in users:
                rows.pop(u, None)
        return out


# ─── Leiden ───────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class LeidenConfig(DetectorConfig):
    detector_type: DetectorType = DetectorType.COMMUNITY
    name: str = "Leiden"
    resolution: float = 1.0  # tuned
    min_community_size: int = 3
    max_community_size: int = 25
    min_density: float = 0.5
    seed: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


class LeidenDetector(BaseDetector):
    incremental = True

    def __init__(self, config: LeidenConfig | None = None, store: GraphStore | None = None):
        super().__init__(config or LeidenConfig(), store)
        self.cfg: LeidenConfig = self._config  # type: ignore[assignment]

    def detect(self, view: GraphView) -> list[RingCandidate]:
        import igraph as ig
        import leidenalg as la

        from fraudsim.detectors.community import CommunityDetector

        edges = CommunityDetector._edge_index(view)
        if not edges:
            return []
        names = sorted({u for e in edges for u in e})
        idx = {u: i for i, u in enumerate(names)}
        items = sorted(edges.items())
        g = ig.Graph(n=len(names), edges=[(idx[u], idx[v]) for (u, v), _ in items])
        part = la.find_partition(g, la.RBConfigurationVertexPartition,
                                 weights=[w for _, w in items],
                                 resolution_parameter=self.cfg.resolution, seed=self.cfg.seed)
        out = []
        for comm in part:
            members = {names[i] for i in comm}
            n = len(members)
            if not self.cfg.min_community_size <= n <= self.cfg.max_community_size:
                continue
            ordered = sorted(members)
            present = sum(1 for i, u in enumerate(ordered) for v in ordered[i + 1:] if (u, v) in edges)
            density = present / (n * (n - 1) / 2)
            if density < self.cfg.min_density:
                continue
            out.append(self._candidate(RingType.MIXED_ATTRIBUTE, members, view, density,
                                       {"algorithm": "leiden", "size": n,
                                        "edge_density": round(density, 4)}))
        return out


# ─── GraphSAGE ────────────────────────────────────────────────────────────────

ATTR_KINDS = ("device", "card", "ip")
N_FEATURES = 12


def graph_tensors(view: GraphView, joined: dict[str, float] | None = None):
    """
    Heterogeneous graph as one homogeneous graph with typed features.
    Nodes: users, then attributes. Edges (both directions): user-attribute links,
    user-user transfers in the window.
    User features: log1p of links per kind (0-2), out/in transfer counts (3-4),
    out/in amounts (5-6), log1p account age (7), is_user (8). Attribute features: kind
    one-hot (0-2), is_attr (9), log1p(global degree) (10). Index 11 is unused (zero).
    """
    users = sorted(view.users)
    uidx = {u: i for i, u in enumerate(users)}
    attrs = sorted({(lk.kind, lk.attr) for lk in view.links})
    aidx = {a: len(users) + i for i, a in enumerate(attrs)}
    n = len(users) + len(attrs)
    x = np.zeros((n, N_FEATURES), dtype=np.float32)
    src, dst = [], []
    per_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for lk in view.links:
        if lk.user not in uidx:
            continue
        k = ATTR_KINDS.index(lk.kind) if lk.kind in ATTR_KINDS else 2
        per_kind[lk.user][k] += 1
        a = aidx[(lk.kind, lk.attr)]
        src += [uidx[lk.user], a]
        dst += [a, uidx[lk.user]]
    out_c, in_c, out_a, in_a = (defaultdict(float) for _ in range(4))
    for t in view.txns:
        if t.sender in uidx and t.receiver in uidx and t.sender != t.receiver:
            out_c[t.sender] += 1
            in_c[t.receiver] += 1
            out_a[t.sender] += t.amount
            in_a[t.receiver] += t.amount
            src += [uidx[t.sender], uidx[t.receiver]]
            dst += [uidx[t.receiver], uidx[t.sender]]
    for u, i in uidx.items():
        x[i, 0:3] = np.log1p(per_kind[u])
        x[i, 3] = math.log1p(out_c[u])
        x[i, 4] = math.log1p(in_c[u])
        x[i, 5] = math.log1p(out_a[u])
        x[i, 6] = math.log1p(in_a[u])
        if joined and u in joined:
            x[i, 7] = math.log1p(max(0.0, view.now_t - joined[u]))
        x[i, 8] = 1.0
    for (kind, aid), i in aidx.items():
        k = ATTR_KINDS.index(kind) if kind in ATTR_KINDS else 2
        x[i, k] = 1.0  # kind one-hot (indices 0-2 are per-kind link counts for users)
        x[i, 9] = 1.0  # is_attr
        x[i, 10] = math.log1p(view.attr_degree.get((kind, aid), 1))
    ei = np.array([src, dst], dtype=np.int64) if src else np.zeros((2, 0), dtype=np.int64)
    return users, x, ei


def make_sage(hidden: int = 64, dropout: float = 0.2):
    import torch
    from torch import nn

    class Sage(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.l1s, self.l1n = nn.Linear(N_FEATURES, hidden), nn.Linear(N_FEATURES, hidden, bias=False)
            self.l2s, self.l2n = nn.Linear(hidden, hidden), nn.Linear(hidden, hidden, bias=False)
            self.out = nn.Linear(hidden, 1)
            self.drop = nn.Dropout(dropout)

        @staticmethod
        def mean_agg(h, ei, n):
            agg = torch.zeros(n, h.shape[1])
            if ei.shape[1]:
                agg.index_add_(0, ei[1], h[ei[0]])
                deg = torch.bincount(ei[1], minlength=n).clamp(min=1).unsqueeze(1).float()
                agg = agg / deg
            return agg

        def forward(self, x, ei):
            n = x.shape[0]
            h = torch.relu(self.l1s(x) + self.l1n(self.mean_agg(x, ei, n)))
            h = self.drop(h)
            h = torch.relu(self.l2s(h) + self.l2n(self.mean_agg(h, ei, n)))
            return self.out(self.drop(h)).squeeze(-1)

    return Sage()


# Callables hook(detector, view, scores) run after each GraphSAGE scoring call; used only by the
# round-4 guard controls to record drift statistics. Empty in every other experiment.
DETECT_HOOKS: list = []


def _beta_thetas(order: int) -> list[list[float]]:
    """Coefficients of the Beta-wavelet polynomials in L (BWGNN, Tang et al. 2022, calculate_theta2)."""
    from math import comb

    from scipy.special import beta

    out = []
    for i in range(order + 1):
        # (x/2)^i (1 - x/2)^(order-i) / B(i+1, order+1-i), expanded in powers of x
        coef = [0.0] * (order + 1)
        for j in range(order - i + 1):
            c = comb(order - i, j) * ((-0.5) ** j) * (0.5 ** i)
            coef[i + j] += c
        b = beta(i + 1, order + 1 - i)
        out.append([float(c / b) for c in coef])
    return out


def make_bwgnn(hidden: int = 64, order: int = 2, **_):
    """BWGNN (homogeneous), following the authors' BWGNN.py: MLP, C+1 Beta-wavelet filters on the
    symmetric normalised Laplacian, concatenation, MLP. Reference re-implementation without DGL."""
    import torch
    from torch import nn

    thetas = _beta_thetas(order)

    class BWGNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.l1, self.l2 = nn.Linear(N_FEATURES, hidden), nn.Linear(hidden, hidden)
            self.l3, self.l4 = nn.Linear(hidden * len(thetas), hidden), nn.Linear(hidden, 1)

        @staticmethod
        def lap(h, ei, dinv):
            # L h = h - D^-1/2 A D^-1/2 h  (ei holds both directions of every undirected edge)
            m = torch.zeros_like(h)
            if ei.shape[1]:
                m.index_add_(0, ei[1], (h * dinv)[ei[0]])
            return h - m * dinv

        def forward(self, x, ei):
            n = x.shape[0]
            deg = torch.bincount(ei[1], minlength=n).clamp(min=1).float() if ei.shape[1] else torch.ones(n)
            dinv = deg.pow(-0.5).unsqueeze(1)
            h = torch.relu(self.l2(torch.relu(self.l1(x))))
            powers = [h]
            for _ in range(order):
                powers.append(self.lap(powers[-1], ei, dinv))
            outs = [sum(t * p for t, p in zip(th, powers, strict=True)) for th in thetas]
            h = torch.relu(self.l3(torch.cat(outs, -1)))
            return self.l4(h).squeeze(-1)

    return BWGNN()


@dataclass(slots=True)
class GnnConfig(DetectorConfig):
    detector_type: DetectorType = DetectorType.COMMUNITY
    name: str = "GraphSAGE"
    model_path: str = "results/w2_gnn/graphsage.pt"
    node_threshold: float = 0.5  # tuned
    # Inside the incremental pipeline (hybrid), run on the whole graph as a full-graph
    # detector instead of on the dirty region (the GNN needs 2-hop context of every node).
    as_full_detector: bool = False
    min_ring_size: int = 3
    max_ring_size: int = 25
    # "any": components over any shared attribute or transfer (the baseline's rule).
    # "evidence": the EvidGNN ring rule (ablation A3, docs/research/evidgnn_protocol.md).
    ring_rule: str = "any"
    extra: dict[str, Any] = field(default_factory=dict)


class GnnDetector(BaseDetector):
    incremental = True

    def __init__(self, config: GnnConfig | None = None, store: GraphStore | None = None):
        super().__init__(config or GnnConfig(), store)
        self.cfg: GnnConfig = self._config  # type: ignore[assignment]
        self._model = None
        if self.cfg.as_full_detector:
            self.incremental = False

    def _load(self):
        if self._model is None:
            import torch

            from fraudsim.experiments.harness import ROOT

            state = torch.load(ROOT / self.cfg.model_path, weights_only=False)
            hp = dict(state["hparams"])
            arch = hp.pop("arch", "sage")
            m = make_bwgnn(**hp) if arch == "bwgnn" else make_sage(**hp)
            m.load_state_dict(state["state_dict"])
            m.eval()
            self._model = (m, state["mean"], state["std"])
        return self._model

    def node_scores(self, view: GraphView) -> dict[str, float]:
        from fraudsim.detectors import evidgnn as _eg  # shared per-stream cache (threshold-free)

        key = None
        if _eg.SCORE_CACHE is not None:
            key = ("graphsage", self.cfg.model_path, view.now_t, view.since_t,
                   len(view.users), len(view.links), len(view.txns))
            if key in _eg.SCORE_CACHE:
                return _eg.SCORE_CACHE[key]
        out = self._node_scores(view)
        if key is not None:
            _eg.SCORE_CACHE[key] = out
        return out

    def _node_scores(self, view: GraphView) -> dict[str, float]:
        import torch

        model, mean, std = self._load()
        joined = self.store.joined(set(view.users)) if self.store is not None else None
        users, x, ei = graph_tensors(view, joined)
        if not users:
            return {}
        xs = torch.from_numpy((x - mean) / std)
        with torch.no_grad():
            p = torch.sigmoid(model(xs, torch.from_numpy(ei))).numpy()
        return {u: float(p[i]) for i, u in enumerate(users)}

    def detect(self, view: GraphView) -> list[RingCandidate]:
        cfg = self.cfg
        scores = self.node_scores(view)
        self.last_scores = scores  # read by the fused ring scorer (evidgnn_protocol.md, amendment 2)
        if scores:  # share of active users at p >= 0.5, per scoring call (anchor_protocol.md guard)
            hist = self.__dict__.setdefault("flag_history", [])
            hist.append(sum(1 for p in scores.values() if p >= 0.5) / len(scores))
        for hook in DETECT_HOOKS:  # extra trigger statistics (round4_protocol.md, I3); empty by default
            hook(self, view, scores)
        flagged = {u for u, p in scores.items() if p >= cfg.node_threshold}
        if len(flagged) < cfg.min_ring_size:
            return []
        if cfg.ring_rule == "evidence":
            from fraudsim.detectors.evidgnn import evidence_rings

            return [self._candidate(RingType.MIXED_ATTRIBUTE, comp, view, risk,
                                    {"algorithm": "graphsage", "rule": "evidence", "mean_node_p": round(risk, 4)})
                    for comp, risk in evidence_rings(view, scores, flagged, cfg.min_ring_size, cfg.max_ring_size)]
        adj: dict[str, set[str]] = defaultdict(set)
        for links in view.links_by_attr().values():
            us = sorted({lk.user for lk in links} & flagged)
            for i, u in enumerate(us):
                for v in us[i + 1:]:
                    adj[u].add(v)
                    adj[v].add(u)
        for t in view.txns:
            if t.sender in flagged and t.receiver in flagged and t.sender != t.receiver:
                adj[t.sender].add(t.receiver)
                adj[t.receiver].add(t.sender)
        seen: set[str] = set()
        out = []
        for u in sorted(flagged):
            if u in seen or u not in adj:
                continue
            comp, stack = set(), [u]
            while stack:
                a = stack.pop()
                if a in comp:
                    continue
                comp.add(a)
                stack.extend(adj[a] - comp)
            seen |= comp
            if cfg.min_ring_size <= len(comp) <= cfg.max_ring_size:
                risk = float(np.mean([scores[m] for m in comp]))
                out.append(self._candidate(RingType.MIXED_ATTRIBUTE, comp, view, risk,
                                           {"algorithm": "graphsage", "mean_node_p": round(risk, 4)}))
        return out
