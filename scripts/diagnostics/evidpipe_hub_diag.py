"""Amendment 3 diagnosis: which detector proposed EvidPipe's alerted false rings at large hubs,
and what the fused scorer saw. Writes docs/research/gnn/evidpipe_hub_diag.json."""
from __future__ import annotations

import json
from collections import Counter

import numpy as np

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.experiments import evidgnn as e
from fraudsim.experiments.harness import ROOT, make_stream
from fraudsim.experiments.large_hubs import overrides as hub_ov
from fraudsim.experiments.w2_baselines import skip_explanations
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.metrics.matching import jaccard


def main() -> None:
    skip_explanations()
    sel = json.loads(e.SELECTED.read_text())
    m = e.systems(sel, ["evidpipe"])[0]
    out = {}
    for seed in (4201, 4202, 4203):
        stream = make_stream("hub_heavy", seed, hub_ov(500))
        store = InMemoryGraphStore()
        stage = e.FusedStage(scorer=e.load_fused(ROOT / m.model_path), record=True)
        stage.policy.default_threshold = m.alert_threshold
        eng = DetectionEngine(store, build_detectors(store, m.overrides), tracker=RingTracker(EnsembleConfig()),
                              config=EngineConfig(batch_size=50, full_interval_s=0.0), scorer=stage)
        eng.run(stream.events)
        truth = [{u for _, a, u in r.member_history if a == "join"} for r in stream.generator.ledger.rings.values()]
        fp = [r for r in eng.tracker.rings.values() if r.alerted_at is not None
              and max((jaccard(set(r.members), g) for g in truth), default=0) < 0.5]
        det = Counter("+".join(sorted(r.sources)) for r in fp)
        sizes = [len(r.members) for r in fp]
        feats = [row["features"][-3:] for row in stage.rows]
        out[seed] = {"false_alerted": len(fp), "by_detectors": dict(det),
                     "size_median": float(np.median(sizes)) if sizes else None,
                     "risk_median": float(np.median([r.risk for r in fp])) if fp else None,
                     "gnn_mean_p_median_all_scored": float(np.median([f[0] for f in feats])) if feats else None}
        print(seed, out[seed], flush=True)
    (ROOT / "docs/research/gnn/evidpipe_hub_diag.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
