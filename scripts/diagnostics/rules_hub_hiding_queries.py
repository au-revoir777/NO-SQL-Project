"""Round 3 R1 diagnostic: which static rule (Q1-Q4) produced each hub-hiding ring that the scored
rules (cap 10, cycle rule) detect on hub_heavy, seeds 3001-3020 (the cap-sweep block)."""
from __future__ import annotations

import json
from collections import Counter

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments.followups import scored_rules
from fraudsim.experiments.harness import ROOT, make_stream
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.metrics.matching import jaccard
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage


def main() -> None:
    m = scored_rules()
    scorer = RingScorer.load(ROOT / m.model_path)
    found, missed, shared_kind = Counter(), 0, Counter()
    for seed in range(3001, 3021):
        stream = make_stream("hub_heavy", seed)
        store = InMemoryGraphStore()
        stage = ScoringStage(scorer=scorer)
        stage.policy.default_threshold = m.alert_threshold
        eng = DetectionEngine(store, build_detectors(store, m.overrides), tracker=RingTracker(EnsembleConfig()),
                              config=EngineConfig(batch_size=50, full_interval_s=5.0), scorer=stage)
        eng.run(stream.events)
        for r in stream.generator.ledger.rings.values():
            if r.evasion_mode.value != "hub_hiding":
                continue
            truth = {u for _, a, u in r.member_history if a == "join"}
            hit = [t for t in eng.tracker.rings.values() if t.alerted_at is not None and jaccard(set(t.members), truth) >= 0.5]
            if not hit:
                missed += 1
                continue
            qs = {h.get("evidence", {}).get("query") for h in hit[0].history if isinstance(h, dict)}
            qs |= {hit[0].evidence.get("query")}
            q = "+".join(sorted(x for x in qs if x)) or "unknown"
            found[q] += 1
            shared_kind[str(hit[0].ring_type)] += 1
    out = {"found_by_query": dict(found), "ring_type": dict(shared_kind), "missed": missed}
    print(out)
    (ROOT / "docs/research/round3_rules_hub_hiding.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
