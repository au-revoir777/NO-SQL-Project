# E1b and E3b results

Protocol: `docs/research/e1b_protocol.md` (committed before any result, 0e0ff69).
Tables: `docs/research/e1b_tables.md` (generated). Runs: `results/e1b_tuning/`,
`results/e1b_scored_baselines/` and `results/e3b_frontier_ci/`, all recorded on a clean
tree (git commit fcd9d1f, `git_dirty: false`). Every E1b stream digest equals
E1's for the same scenario and seed (50 of 50), so all comparisons are paired.

## Thresholds selected on validation seeds 301-303

| Method | Selected alert threshold | Mean validation F1 |
|---|---|---|
| Static Cypher cap 10 + scorer | 0.5 | 0.599 |
| Static Cypher cap 100 + scorer | 0.5 | 0.574 |
| Louvain + scorer | 0.3 | 0.425 |

The curves are flat between 0.3 and 0.8 for the static rules and from 0.3 up
for Louvain, so the choice matters little.

## E1b: Table II with scored baselines (5 scenarios x seeds 1001-1010)

| Method | P | R | F1 | Holm p vs proposed | d_z |
|---|---|---|---|---|---|
| Cap 10, no scorer | 0.14 | 0.61 | 0.21 | <0.001 | 3.86 |
| Cap 10 + scorer | 0.64 | 0.53 | 0.56 | <0.001 | 0.94 |
| Cap 100, no scorer | 0.12 | 0.61 | 0.19 | <0.001 | 4.22 |
| Cap 100 + scorer | 0.63 | 0.48 | 0.52 | <0.001 | 1.25 |
| Louvain, no scorer | 0.39 | 0.33 | 0.29 | <0.001 | 1.82 |
| Louvain + scorer | 0.81 | 0.32 | 0.41 | <0.001 | 1.19 |
| Proposed | 0.76 | 0.74 | 0.73 | - | - |

Reading:

- The scorer is most of the headline gain. For cap 10 it raises F1 from 0.21 to
  0.56 (precision 0.14 to 0.64, recall 0.61 to 0.53).
- The candidate generator (hub-aware rule with incremental detection) adds the
  rest, 0.56 to 0.73, almost entirely as recall (0.53 to 0.74), and this
  difference is significant (Holm p < 0.001, d_z 0.94).
- Louvain gains precision from the scorer (0.39 to 0.81) but no recall; its
  communities rarely coincide with rings, so there is little for the scorer to rescue.
- Caveat: the shipped scorer was trained on the proposed pipeline's candidates.

## E3b: frontier intervals (existing E3 runs; 4 scenarios x seeds 1001-1005)

- Best F1 with the scorer on shared-attribute rings: hub-aware 0.583 (alert 0.8)
  vs cap 10 at 0.554 (alert 0.7).
- Difference +0.029, 95% bootstrap interval [-0.030, +0.097] (2,000 resamples,
  stratified by scenario, best threshold re-selected per resample); hub-aware
  better in 84% of resamples. Per-run paired Wilcoxon p = 0.66 (n = 20).
- At the best operating point the two mechanisms are therefore not
  distinguishable on F1. Hub weighting's measured advantage is recall the cap
  cannot reach (0.81 vs at most 0.53), not F1 at the best threshold.

## Consequences for the paper (refinement issue P1)

The abstract, the RQ1 paragraph, the Table II caption, the frontier paragraph and
caption, C3, the conclusion and the Baselines threat are reworded to attribute
the gain separately to the scorer and the candidate generator. P2 (statistical
support for C1) follows from E3b: on F1, the hub weight's advantage over the cap
is not established.
