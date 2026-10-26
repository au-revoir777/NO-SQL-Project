"""
Follow-up experiments of prompt 2 (docs/research/followups_protocol.md).

    python -m fraudsim.experiments.followups nd          # N-D evidence-count rule, seeds 2401-2420
    python -m fraudsim.experiments.followups r2          # scored rules arms for Figs 6-8, Table III
    python -m fraudsim.experiments.followups r6          # widened grids, validation seeds
    python -m fraudsim.experiments.followups r5          # 10,000 users, seeds 2501-2505
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from fraudsim.experiments.harness import PROPOSED, ROOT, Method, _append, _merge, make_stream, run_grid
from fraudsim.experiments.tuning import load_tuned

OUT = ROOT / "results"
SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
ND_SEEDS = tuple(range(2401, 2421))
R5_SEEDS = tuple(range(2501, 2506))


def _alert() -> float:
    return float(load_tuned()["alert_threshold"])


def nd_methods() -> list[Method]:
    def m(name: str, hub: dict) -> Method:
        return Method(f"nd_{name}", name, _merge(PROPOSED, {"hub_aware": hub}), family="nd",
                      alert_threshold=_alert())

    return [
        m("log_one", {"weight_method": "inverse_log_degree", "edge_threshold": 0.3}),
        m("log_two", {"weight_method": "inverse_log_degree", "edge_threshold": 0.3, "max_attr_weight": 0.29}),
        m("const_one", {"weight_method": "none", "edge_threshold": 0.5}),
        m("const_two", {"weight_method": "none", "edge_threshold": 1.0}),
    ]


def nd() -> None:
    run_grid("nd_evidence_count", SCENARIOS, ND_SEEDS, nd_methods(), OUT)


def scored_rules() -> Method:
    from fraudsim.experiments.w2_baselines import make

    m = make("rules", "10_1", 0.7)
    m.name, m.label = "rules_own_scorer", "rules (cap 10, cycle) + own scorer, alert 0.7"
    return m


def r2() -> None:
    from fraudsim.experiments.suite import HUB_SIZES, _rings_of_size

    m = [scored_rules()]
    seeds5, seeds10 = list(range(1001, 1006)), list(range(1001, 1011))
    run_grid("r2_scored_rules/table3", SCENARIOS, seeds10, m, OUT)
    for size in HUB_SIZES:
        run_grid("r2_scored_rules/e5", ["hub_heavy"], seeds5, m, OUT,
                 scenario_overrides={"simulation.hub_distribution.mega_office_gateway.size": size,
                                     "simulation.num_users": max(100, size + 50)},
                 extra_columns={"hub_size": size})
    from fraudsim.experiments.large_hubs import HUB_SIZES as LH, overrides

    for size in LH:
        run_grid("r2_scored_rules/e5b", ["hub_heavy"], seeds5, m, OUT, scenario_overrides=overrides(size),
                 extra_columns={"hub_size": size})
    for rate in (10, 25, 50, 100):
        run_grid("r2_scored_rules/e6", ["adversarial"], seeds5, m, OUT,
                 scenario_overrides={"simulation.target_event_rate": rate},
                 extra_columns={"sweep": "event_rate", "value": rate})
    for size in (3, 4, 6, 8):
        run_grid("r2_scored_rules/e6", ["baseline"], seeds5, m, OUT,
                 scenario_overrides={"rings": _rings_of_size(size)},
                 extra_columns={"sweep": "ring_size", "value": size})


def r6() -> None:
    from fraudsim.experiments.weight_functions import method

    ms = [method("inverse_degree_plain", e, f"_e{e}") for e in (0.02, 0.05)]
    ms += [method("soft_cap", e, f"_e{e}") for e in (1.2, 1.5, 2.0)]
    run_grid("r6_grid", SCENARIOS, (301, 302, 303), ms, OUT)


def r5() -> None:
    from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
    from fraudsim.experiments.timer_baselines import scale_overrides
    from fraudsim.graph.store import InMemoryGraphStore
    from fraudsim.metrics.evaluation import detect_ms

    out = OUT / "r5_scale"
    out.mkdir(parents=True, exist_ok=True)
    off = {"static_cypher": {"enabled": False}, "community": {"enabled": False}}
    modes = {"incremental": {"incremental": True}, "timer_5": {"incremental": False, "full_timer_s": 5.0}}
    t0 = time.perf_counter()
    for n in (10000,):
        for seed in R5_SEEDS:
            stream = make_stream("scale_sweep", seed, scale_overrides(n))
            start = stream.generator.ts(0.0)
            head = [e for e in stream.events if (e.ts - start).total_seconds() < 10]
            tail = stream.events[len(head):]
            span = (tail[-1].ts - tail[0].ts).total_seconds() if tail else 0.0
            for mode, cfg in modes.items():
                store = InMemoryGraphStore()
                store.apply(head)
                engine = DetectionEngine(store, build_detectors(store, off), config=EngineConfig(**cfg))
                engine.run(tail)
                ran = [r for r in engine.reports if r.detector_ms]
                det = sorted(detect_ms(r) for r in ran)
                regions = sorted(r.region for r in ran)
                _append(out / "results.csv", {
                    "experiment": "r5_scale", "users": n, "seed": seed, "mode": mode,
                    "stream_digest": stream.generator.digest[:16], "passes": len(ran),
                    "region_p50": regions[len(regions) // 2] if regions else 0,
                    "detect_ms_p50": round(det[len(det) // 2], 3) if det else 0.0,
                    "detect_ms_sum": round(sum(det), 3), "sim_s": round(span, 3),
                    "ms_per_sim_s": round(sum(det) / span, 3) if span else None})
                print(f"[r5] {n} {seed} {mode} {sum(det) / span:.0f} ms/sim-s ({time.perf_counter() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    {"nd": nd, "r2": r2, "r6": r6, "r5": r5}[sys.argv[1]]()
