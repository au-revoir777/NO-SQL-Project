"""
Diagnostic trace (prompt 2, N1 follow-up): why do incremental and full recomputation
differ at large hubs, and why does a constant weight lose rings under the 250 limit?

Runs the incremental and full engines in lockstep on the same E5b stream
(hub_heavy, office hub resized; seeds 1001-1005 already used as test seeds in E5b).
Produces no result for any paper table: output goes to docs/paper/refine2/diag/.

    python scripts/diagnostics/trace_region.py --weight inverse_log_degree --edge 0.3 --seed 1002
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
from fraudsim.detectors.ensemble import EnsembleConfig, RingTracker
from fraudsim.detectors.hubaware import HubAwareSharedAttribute
from fraudsim.detectors.runner import hub_degrees
from fraudsim.experiments.harness import DEFAULT_MODEL, PROPOSED, _merge, make_stream
from fraudsim.experiments.large_hubs import overrides
from fraudsim.experiments.tuning import load_tuned
from fraudsim.graph.store import InMemoryGraphStore
from fraudsim.metrics.evaluation import all_members, evaluate_run, true_rings
from fraudsim.scoring.scorer import RingScorer
from fraudsim.scoring.stage import ScoringStage

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/paper/refine2/diag"


def jac(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def build(weight: str, edge: float, incremental: bool, scorer: RingScorer):
    store = InMemoryGraphStore()
    over = _merge(PROPOSED, {"hub_aware": {"weight_method": weight, "edge_threshold": edge}})
    cfg = EngineConfig(batch_size=50, full_interval_s=5.0, incremental=incremental)
    stage = ScoringStage(scorer=scorer)
    stage.policy.default_threshold = float(load_tuned()["alert_threshold"])
    eng = DetectionEngine(
        store, build_detectors(store, over), tracker=RingTracker(EnsembleConfig()),
        config=cfg, scorer=stage,
    )
    hub = next(d for d in eng.detectors if isinstance(d, HubAwareSharedAttribute))
    log: dict[str, list] = {"cands": [], "region": [], "seeds": [], "view": []}
    orig_detect = hub.detect

    def detect(view):
        found = orig_detect(view)
        log["cands"].append([frozenset(c.members) for c in found])
        log["view"] = [view]  # keep only the latest view (memory)
        return found

    hub.detect = detect  # type: ignore[method-assign]
    orig_expand = store.expand

    def expand(seeds, *a, **k):
        r = orig_expand(seeds, *a, **k)
        log["seeds"].append(set(seeds))
        log["region"].append(set(r))
        return r

    store.expand = expand  # type: ignore[method-assign]
    return eng, hub, log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weight", default="inverse_log_degree")
    ap.add_argument("--edge", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=1002)
    ap.add_argument("--hub", type=int, default=500)
    a = ap.parse_args()

    stream = make_stream("hub_heavy", a.seed, overrides(a.hub))
    scorer = RingScorer.load(DEFAULT_MODEL)
    inc, hub_i, log_i = build(a.weight, a.edge, True, scorer)
    full, hub_f, log_f = build(a.weight, a.edge, False, scorer)
    truth = true_rings(stream.generator.ledger)
    members = {r.ring_id: all_members(r) for r in truth}

    events: list[dict] = []
    for b, batch in enumerate(inc.batches(stream.events)):
        inc.process(batch)
        full.process(batch)
        ci, cf = log_i["cands"][-1], log_f["cands"][-1]
        for rid, mem in members.items():
            bi = max((jac(c, mem) for c in ci), default=0.0)
            bf = max((jac(c, mem) for c in cf), default=0.0)
            if bf >= 0.5 and bi < 0.5:
                # full sees the ring this batch, incremental does not: why?
                cand = max(cf, key=lambda c: jac(c, mem))
                view = log_f["view"][-1]
                pw = hub_f.pair_weights(view)
                region = log_i["region"][-1] if log_i["region"] else set()
                seeds = log_i["seeds"][-1] if log_i["seeds"] else set()
                pairs = []
                for (u, v), w in pw.items():
                    if u in cand and v in cand and w.attr > 0 and w.total >= a.edge:
                        degs = sorted(view.attr_degree.get(x, 0) for x in w.shared)
                        pairs.append({
                            "u": u, "v": v, "attr": round(w.attr, 3), "txn": round(w.txn, 3),
                            "shared_degrees": degs,
                            "n_over_250": sum(d > 250 for d in degs),
                            "u_in_region": u in region, "v_in_region": v in region,
                            "u_seed": u in seeds, "v_seed": v in seeds,
                        })
                events.append({
                    "batch": b, "ring": rid, "jac_full": round(bf, 2), "jac_inc": round(bi, 2),
                    "cand_size": len(cand), "cand_in_region": len(cand & region),
                    "ring_size": len(mem), "seeds_in_cand": len(cand & seeds),
                    "pairs": pairs,
                })

    gen = stream.generator
    s0, s1 = gen.ts(0.0).timestamp(), gen.ts().timestamp()
    det = {}
    for name, eng in (("inc", inc), ("full", full)):
        m = evaluate_run(gen.ledger, eng.tracker, eng.reports, s0, s1, True,
                         hub_degree_of=hub_degrees(gen))
        det[name] = {r["true_ring"]: (bool(r["detected"]), r["evasion"], r["miss_reason"], r["jaccard"]) for r in m.rings}
    OUT.mkdir(parents=True, exist_ok=True)
    tag = f"{a.weight}_e{a.edge}_h{a.hub}_s{a.seed}"
    (OUT / f"trace_{tag}.json").write_text(json.dumps({
        "digest": gen.digest[:16], "detected": det, "full_only_batches": events,
    }, indent=1, default=list))
    # Compact summary line
    diff = {r: (det["inc"][r], det["full"][r])
            for r in det["inc"] if det["inc"][r][0] != det["full"][r][0]}
    reasons: dict[str, int] = defaultdict(int)
    for e in events:
        for p in e["pairs"]:
            key = ("both_out" if not (p["u_in_region"] or p["v_in_region"])
                   else "one_out" if not (p["u_in_region"] and p["v_in_region"]) else "both_in")
            reasons[f"{key}|over250={p['n_over_250']}|txn>0={p['txn'] > 0}"] += 1
    print(json.dumps({"tag": tag, "digest": gen.digest[:16], "ring_diff(inc,full,evasion)": diff,
                      "full_only_batches": len(events), "pair_reasons": dict(reasons)}))
    with (OUT / "summary.csv").open("a", newline="") as fh:
        csv.writer(fh).writerow([tag, gen.digest[:16], json.dumps(diff), len(events),
                                 json.dumps(dict(reasons))])


if __name__ == "__main__":
    main()
