"""
R9 deletion test of alert evidence (docs/research/followups_protocol.md, amendment R9).

For every alert of the shipped pipeline on the E12 test streams (5 scenarios x seeds 1001-1010),
at the moment the alert fires:
- delete each evidence group of the evidence subgraph in turn (links of members to shared
  devices / cards / IPs; transfers among members), recompute the 19 features and the risk;
- control: delete as many member links to *unlisted* attributes (held by one member only);
- compare the group whose deletion lowers the risk most with the group behind the
  explanation's top-ranked feature.

    python -m fraudsim.experiments.deletion_test
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.harness import DEFAULT_MODEL, ROOT, make_stream
from fraudsim.experiments.suite import tuned_proposed
from fraudsim.graph.store import GraphView, InMemoryGraphStore
from fraudsim.scoring.features import RingContext, extract_features
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage

SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
SEEDS = tuple(range(1001, 1011))
GROUP_OF_FEATURE = {
    "share_device": "device", "share_card": "card", "share_ip": "ip",
    "internal_txns_per_member": "transfers", "amount_mean_log": "transfers", "amount_cv": "transfers",
    "near_threshold_frac": "transfers", "cycle_present": "transfers", "cycle_length": "transfers",
}


def _view_without(view: GraphView, members: set[str], group: str, rng=None, n_unlisted: int = 0) -> GraphView:
    holders: dict = {}
    for lk in view.links:
        if lk.user in members:
            holders.setdefault((lk.kind, lk.attr), set()).add(lk.user)
    shared = {a for a, hs in holders.items() if len(hs) >= 2}
    links, txns = list(view.links), list(view.txns)
    if group in ("device", "card", "ip"):
        links = [lk for lk in links if not (lk.user in members and lk.kind == group and (lk.kind, lk.attr) in shared)]
    elif group == "transfers":
        txns = [t for t in txns if not (t.sender in members and t.receiver in members)]
    elif group == "unlisted":
        cand = [i for i, lk in enumerate(links) if lk.user in members and (lk.kind, lk.attr) not in shared]
        drop = set(rng.choice(cand, size=min(n_unlisted, len(cand)), replace=False).tolist()) if cand else set()
        links = [lk for i, lk in enumerate(links) if i not in drop]
    return replace(view, links=links, txns=txns)


class DeletionStage(ScoringStage):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.out: list[dict] = []
        self.rng = np.random.default_rng(0)

    def score_updates(self, engine, updates, now_t, since_t):
        extra = super().score_updates(engine, updates, now_t, since_t)
        for u in extra:
            if u.change != "alert":
                continue
            ring = engine.tracker.rings[u.ring_id]
            feats, view, joined = self.featurize(engine, ring, set(), now_t, since_t)
            ctx = RingContext(ring_id=ring.ring_id, members=ring.members, detectors=set(ring.sources),
                              first_seen_t=ring.first_seen.timestamp(), member_history=ring.size_history,
                              other_flagged_users=set(),
                              cycle_evidence=(ring.evidence.get("by_detector") or {}).get("temporal_cycle"))
            base = float(self.scorer.predict(np.array([feats.to_vector()]))[0])
            contrib = self.scorer.contributions(np.array([feats.to_vector()]))
            top = next((GROUP_OF_FEATURE[f] for f in contrib if f in GROUP_OF_FEATURE), None)
            drops, sizes = {}, {}
            for g in ("device", "card", "ip", "transfers"):
                v2 = _view_without(view, ring.members, g)
                removed = (len(view.links) - len(v2.links)) + (len(view.txns) - len(v2.txns))
                if removed == 0:
                    continue
                f2 = extract_features(ctx, v2, joined)
                drops[g] = base - float(self.scorer.predict(np.array([f2.to_vector()]))[0])
                sizes[g] = removed
            listed_n = sum(sizes.values())
            v3 = _view_without(view, ring.members, "unlisted", self.rng, listed_n)
            unl_removed = len(view.links) - len(v3.links)
            f3 = extract_features(ctx, v3, joined)
            v4 = view
            for g in sizes:
                v4 = _view_without(v4, ring.members, g)
            f4 = extract_features(ctx, v4, joined)
            self.out.append({
                "ring_id": u.ring_id, "members": len(ring.members), "risk": round(base, 4),
                "drop_by_group": {g: round(d, 4) for g, d in drops.items()},
                "removed_by_group": sizes, "explanation_top_group": top,
                "max_drop_group": max(drops, key=drops.get) if drops else None,
                "drop_all_listed": round(base - float(self.scorer.predict(np.array([f4.to_vector()]))[0]), 4),
                "drop_unlisted_control": round(base - float(self.scorer.predict(np.array([f3.to_vector()]))[0]), 4),
                "unlisted_removed": unl_removed, "listed_removed": listed_n,
            })
        return extra


def main() -> None:
    scorer = RingScorer.load(DEFAULT_MODEL)
    m = tuned_proposed()
    rows = []
    for sc in SCENARIOS:
        for seed in SEEDS:
            st = make_stream(sc, seed)
            store = InMemoryGraphStore()
            stage = DeletionStage(scorer=scorer)
            stage.policy.default_threshold = m.alert_threshold
            eng = DetectionEngine(store, build_detectors(store, m.overrides), tracker=RingTracker(EnsembleConfig()),
                                  config=EngineConfig(batch_size=50, full_interval_s=5.0), scorer=stage)
            eng.run(st.events)
            for r in stage.out:
                rows.append({"scenario": sc, "seed": seed, **r})
            print(f"[deletion] {sc} {seed}: {len(stage.out)} alerts", flush=True)
    out = ROOT / "results/r9_deletion"
    out.mkdir(parents=True, exist_ok=True)
    (out / "alerts.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    agree = [r["explanation_top_group"] == r["max_drop_group"] for r in rows if r["explanation_top_group"] and r["max_drop_group"]]
    chance = [1 / len(r["drop_by_group"]) for r in rows if r["explanation_top_group"] and r["drop_by_group"]]
    summary = {
        "alerts": len(rows),
        "agreement_top_feature_vs_max_drop": round(float(np.mean(agree)), 3) if agree else None,
        "agreement_n": len(agree),
        "chance_agreement": round(float(np.mean(chance)), 3) if chance else None,
        "median_drop_all_listed": float(np.median([r["drop_all_listed"] for r in rows])) if rows else None,
        "median_drop_unlisted_control": float(np.median([r["drop_unlisted_control"] for r in rows])) if rows else None,
        "share_unlisted_control_possible": round(float(np.mean([r["unlisted_removed"] > 0 for r in rows])), 3) if rows else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
