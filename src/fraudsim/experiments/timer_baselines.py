"""
E4b: latency against timer-based full recomputation, and scale with hubs that grow
with the population (docs/research/e4b_protocol.md).

    python -m fraudsim.experiments.timer_baselines timer    # E4b-1
    python -m fraudsim.experiments.timer_baselines scale    # E4b-2
    python -m fraudsim.experiments.timer_baselines report   # docs/research/e4b_tables.md
"""

# ruff: noqa: RUF001  (tables use typographic dashes and signs)

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from fraudsim.experiments.harness import ROOT, Method, _append, make_stream, run_grid
from fraudsim.experiments.learned_baselines import paired
from fraudsim.experiments.provenance import recorded
from fraudsim.experiments.suite import tuned_proposed
from fraudsim.metrics.evaluation import detect_ms

ACCURACY_SCENARIOS = ("baseline", "high_noise", "hub_heavy", "adversarial", "drift")
SEEDS = (1001, 1002, 1003, 1004, 1005)
TIMERS = (1.0, 5.0, 30.0)
SCALE_SIZES = (1_000, 5_000, 20_000)
SCALE_SEEDS = (1001, 1002, 1003)


def methods() -> list[Method]:
    inc = tuned_proposed("inc", "incremental (every batch)")
    out = [inc]
    for t in TIMERS:
        m = tuned_proposed(f"timer_{t:g}", f"full graph every {t:g} s")
        m.engine = {"incremental": False, "full_timer_s": t}
        out.append(m)
    return out


def timer(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    return run_grid("e4b_timer", ACCURACY_SCENARIOS, SEEDS, methods(), Path(out), log=log)


def scale_overrides(n: int) -> dict[str, object]:
    f = n / 1000
    return {
        "simulation.num_users": n,
        "simulation.num_devices": int(400 * f),
        "simulation.num_cards": int(400 * f),
        "simulation.num_ips": int(300 * f),
        "simulation.duration_seconds": 20,
        # Hubs grow with the population (protocol E4b-2).
        "simulation.hub_distribution.cloud_proxy.size": int(0.15 * n),
        "simulation.hub_distribution.workplace_network.size": int(0.08 * n),
        "simulation.hub_size_distribution.max_size": int(0.10 * n),
    }


def scale(out: Path = ROOT / "results", log: Callable[[str], None] = print) -> Path:
    from fraudsim.detectors.engine import DetectionEngine, EngineConfig, build_detectors
    from fraudsim.graph.store import InMemoryGraphStore

    out_dir = Path(out) / "e4b_scale_hubs"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "results.csv"
    off = {"static_cypher": {"enabled": False}, "community": {"enabled": False}}
    modes = {
        "incremental": {"incremental": True},
        "full": {"incremental": False},
        "timer_5": {"incremental": False, "full_timer_s": 5.0},
    }
    details = {
        "scenario": "scale_sweep",
        "sizes": list(SCALE_SIZES),
        "seeds": list(SCALE_SEEDS),
        "hub_scaling": {"cloud_proxy": 0.15, "workplace_network": 0.08, "max_size": 0.10},
        "modes": modes,
        "backend": "in_memory",
    }
    t0 = time.perf_counter()
    with recorded(out_dir, "e4b_scale_hubs", details):
        for n in SCALE_SIZES:
            for seed in SCALE_SEEDS:
                stream = make_stream("scale_sweep", seed, scale_overrides(n))
                start = stream.generator.ts(0.0)
                head = [e for e in stream.events if (e.ts - start).total_seconds() < 10]
                tail = stream.events[len(head) :]
                span = (tail[-1].ts - tail[0].ts).total_seconds() if tail else 0.0
                for mode, cfg in modes.items():
                    store = InMemoryGraphStore()
                    store.apply(head)
                    engine = DetectionEngine(
                        store, build_detectors(store, off), config=EngineConfig(**cfg)
                    )
                    engine.run(tail)
                    ran = [r for r in engine.reports if r.detector_ms]
                    det = sorted(detect_ms(r) for r in ran)
                    regions = sorted(r.region for r in ran)
                    row = {
                        "experiment": "e4b_scale_hubs",
                        "run_id": f"e4b_scale_hubs:{n}:{seed}:{mode}",
                        "users": n,
                        "seed": seed,
                        "mode": mode,
                        "stream_digest": stream.generator.digest[:16],
                        "events_total": len(stream.events),
                        "batches": len(engine.reports),
                        "passes": len(ran),
                        "region_p50": regions[len(regions) // 2] if regions else 0,
                        "detect_ms_p50": round(det[len(det) // 2], 3) if det else 0.0,
                        "detect_ms_p95": round(det[int(len(det) * 0.95)], 3) if det else 0.0,
                        "detect_ms_sum": round(sum(det), 3),
                        "sim_s": round(span, 3),
                        "ms_per_sim_s": round(sum(det) / span, 3) if span else None,
                    }
                    _append(path, row)
                    log(
                        f"[e4b_scale] users={n} seed={seed} {mode:11s} "
                        f"region={row['region_p50']} p50={row['detect_ms_p50']}ms "
                        f"cost={row['ms_per_sim_s']}ms/s ({time.perf_counter() - t0:.0f}s)"
                    )
    return path


def report(out_md: Path = ROOT / "docs/research/e4b_tables.md") -> None:
    lines = ["# E4b tables (generated)", ""]
    tp = ROOT / "results/e4b_timer/results.csv"
    if tp.exists():
        df = pd.read_csv(tp)
        df["f1"] = df["f1"].fillna(0)
        df["cost"] = df["detect_ms_sum"] / df["sim_s"]
        lines += [
            "## E4b-1: timer-based full recomputation (5 scenarios × seeds 1001-1005)",
            "",
            "| Method | F1 | TTD p50 (s) | Cost (ms per simulated s) | p F1 | p TTD |",
            "|---|---|---|---|---|---|",
        ]
        ref = df[df["method"] == "inc"].set_index(["scenario", "seed"]).sort_index()
        for m in ["inc", *[f"timer_{t:g}" for t in TIMERS]]:
            g = df[df["method"] == m].set_index(["scenario", "seed"]).sort_index()
            if g.empty:
                continue
            pf = pt = "–"
            if m != "inc":
                pf = str(paired(ref["f1"].to_list(), g["f1"].to_list())["p"])
                both = ref["ttd_p50_s"].notna() & g["ttd_p50_s"].notna()
                pt = str(
                    paired(
                        ref.loc[both, "ttd_p50_s"].to_list(), g.loc[both, "ttd_p50_s"].to_list()
                    )["p"]
                )
            lines.append(
                f"| {m} | {g['f1'].mean():.2f} | {g['ttd_p50_s'].median():.1f} | "
                f"{g['cost'].mean():.1f} | {pf} | {pt} |"
            )
        lines.append("")
    sp = ROOT / "results/e4b_scale_hubs/results.csv"
    if sp.exists():
        df = pd.read_csv(sp)
        g = df.groupby(["users", "mode"]).agg(
            n=("seed", "count"),
            region=("region_p50", "median"),
            p50=("detect_ms_p50", "mean"),
            p50_min=("detect_ms_p50", "min"),
            p50_max=("detect_ms_p50", "max"),
            cost=("ms_per_sim_s", "mean"),
        )
        lines += [
            "## E4b-2: scale_sweep with hubs growing with the population (seeds 1001-1003)",
            "",
            "| Users | Mode | n | Region p50 | ms per batch/pass p50 (mean; min–max)"
            " | Cost (ms per simulated s) |",
            "|---|---|---|---|---|---|",
        ]
        for (u, mode), r in g.iterrows():
            lines.append(
                f"| {u:,} | {mode} | {int(r['n'])} | {r['region']:.0f} | {r['p50']:.1f} "
                f"({r['p50_min']:.1f}–{r['p50_max']:.1f}) | {r['cost']:.1f} |"
            )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_md}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["timer", "scale", "report"])
    {"timer": timer, "scale": scale, "report": report}[ap.parse_args().step]()


if __name__ == "__main__":
    main()
