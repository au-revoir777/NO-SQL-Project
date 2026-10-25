# E4b: latency claims against realistic baselines

Committed before any E4b result exists. Motivation: refinement issue P4
(`docs/paper/paper_refinement_prompt.md`). The 623x speed-up of E4 compares the
incremental engine with full recomputation on every 50-event batch, which no
deployment would run. It used 3 seeds, the incremental interval is wider than
its mean, and the 50k and 100k full-recompute numbers are confounded by memory
pressure. Hub sizes in `scale_sweep` stay fixed while the population grows, so
the region shrinks by construction. And time to detect is no better than the
timer-driven static rules (9.3 s vs 9.5 s).

## E4b-1: timer-based full recomputation (accuracy, TTD and cost)

- Scenarios baseline, high_noise, hub_heavy, adversarial, drift; seeds
  1001-1005 (the first five E1 streams).
- Methods, all with the proposed detectors, tuned thresholds and the shipped scorer:
  - `inc`: the shipped incremental engine (every batch, dirty region);
  - `timer_1`, `timer_5`, `timer_30`: the same detectors on the *whole* graph,
    once every 1, 5 or 30 simulated seconds, and not in between.
- Metrics: ring precision, recall, F1; time to detect (median per run); detection
  cost per simulated second (sum of region expansion, view and detector time
  over the run, divided by the simulated duration); median cost of one pass.
- Comparison: each timer arm against `inc` on paired runs (Wilcoxon on F1 and
  on TTD).

## E4b-2: scale with hubs that grow with the population

- `scale_sweep` at 1,000, 5,000 and 20,000 users, seeds 1001-1003 (E4's sizes up
  to 20,000; the 50k and 100k points are left out because of memory pressure on
  the 7.7 GB machine).
- Hub sizes proportional to the population: `cloud_proxy` 15% of users,
  `workplace_network` 8%, and the generated hub-size distribution capped at 10%
  of users instead of 100. Devices, cards and IPs scale as in E4.
- Modes: incremental (every batch), full recomputation every batch, and a 5 s
  timer (as in E4b-1).
- Metrics: as in E4 (median and p95 detection ms per batch or pass, median
  region size), plus detection cost per simulated second.

## Reporting rules fixed in advance

- The every-batch speed-up is reported as a worst-case bound, not a headline.
- The paper's main latency comparison becomes cost per simulated second and TTD
  against the timer baselines.

## Outputs

`results/e4b_timer/`, `results/e4b_scale_hubs/`, `docs/research/e4b_tables.md`
(generated), `docs/research/e4b_results.md`.

Amendments, if any, are appended below with their reason.
