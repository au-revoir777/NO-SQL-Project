# W2/W3 protocol: existing-method baselines with their own scorers

Committed before any W2 training, tuning or evaluation run. Amendments are appended with reasons.

## Question

Does the proposed pipeline outperform existing graph fraud and community methods when each gets the same object definition, the same tracker, a scorer trained on its own candidates, and the same tuning budget, on test seeds no one has seen?

## Methods

All methods emit rings of 3–25 users into the same `RingTracker` (two consecutive hits to confirm, three misses to dissolve). They are scored by a logistic-regression + isotonic scorer trained on **that method's own candidates**, with the shipped protocol: seeds 101–110 × six training scenarios; the first 70% of each run fits the regression, the rest fits the calibrator. The structural parameter is at its default during scorer training.

| Key | Method | What it represents | Code | Runs | Structural parameter (10–14 grid points) |
|---|---|---|---|---|---|
| `proposed` | shipped pipeline | ours | this repo | dirty region per batch | θ_e (already selected: 0.3; shipped scorer, which is its own) |
| `peeling` | FRAUDAR-style greedy peeling, 1/log(deg+5) column weights, users × {attributes, money partners}; blocks extracted iteratively (≤10 per pass) | FRAUDAR (Hooi et al., KDD 2016). Its output equals Spade's, which maintains the same peeling incrementally (Jiang et al., PVLDB 16, VERIFY) | reimplemented (`detectors/external.py`); Spade's C++ code is public (github.com/samjjx/Spade, VERIFY), not run | whole graph every batch | minimum block score g ∈ {0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 0.8, 1.0, 1.3} |
| `leiden` | Leiden communities on the Louvain baseline's projection, same size and density filter | Leiden (Traag et al., 2019); incremental Leiden variants aim at the same partitions with less work | `leidenalg` 0.12 | whole graph every batch | resolution ∈ {0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8, 12} |
| `louvain` | the paper's Louvain baseline, resolution tuned | Louvain (Blondel et al., 2008) | networkx 3.5 | 5 s timer (as in the paper) | resolution, same grid |
| `rules` | Static Cypher Q1–Q4 | the original rules | this repo | 5 s timer | cap ∈ {3, 5, 10, 20, 50, 100, 200} × cycle rule on/off (14) |
| `rules_per_scenario` | as `rules`, with (cap, cycle, θ_a) chosen per scenario on validation | strongest rule baseline (uses scenario identity: an oracle advantage) | | | same grid, per scenario |
| `gnn` | GraphSAGE (mean aggregator, 2 layers, hidden 64), node classification of users on the user–attribute–transfer graph; fixed node-to-ring rule: connected components over shared attributes and transfers among flagged users, size 3–25 | GNN fraud detection (e.g. GraphSAGE as used by Badjie et al., Kumar et al.) | `torch` 2.5.1 CPU | whole graph every batch | node threshold ∈ {0.1, …, 0.9, 0.95} |
| `gnn_unscored` | `gnn` without a ring scorer | GNN alone | | | same grid |
| `gb_louvain` | gradient boosting over Louvain groups (E13, existing model and threshold) | learned tabular baseline | this repo | 5 s timer | none (as in E13) |

GraphSAGE training:
- Snapshots of the whole active graph every 5 simulated seconds, on seeds 101–110 × the six training scenarios.
- Label: user is a current member of a spawned, undissolved planted ring (ground-truth ledger; training only).
- BCE with positive-class weighting, Adam (lr 0.005, weight decay 5e-4), 40 epochs, torch seed 0, features standardised on training data.
- Node features use no hub weighting and no ring features: link counts per attribute kind, transfer counts and amounts, account age; attributes carry kind and log degree, so the GNN can learn its own hub discount.
- Training cost and label requirement are reported.

## Tuning (equal or larger budget for baselines)

- Validation seeds 301–303 × five accuracy scenarios.
- Each baseline: structural grid × θ_a ∈ {0.2, 0.3, 0.5, 0.7, 0.8, 0.9}, jointly: 60 points (84 for rules). Selection: max mean ring F1.
- The proposed method keeps its shipped selection (5 θ_e × 6 θ_a = 30 points on the same seeds). So baselines get at least the proposed method's budget.
- Grids are tabulated in the results, and selections on a grid edge are reported.

## Evaluation

- Fresh test seeds **2101–2120** × five accuracy scenarios: 100 paired runs per method. Never used before, and used once.
- Locked environment (`requirements-lock.txt`, plus `torch==2.5.1+cpu`, `leidenalg==0.12.0`, `igraph==1.0.0`).
- Metrics:
  - primary: ring F1 at the validation-selected operating point, pooled (scenario-weighted) and per scenario;
  - also: precision, recall, recall by evasion strategy, TTD, ms per batch;
  - threshold-free: ring PR AUC where the harness records it.

## Hypotheses and tests

**Confirmatory (paper family member 1):** `proposed` − strongest baseline, in ring F1, two-sided.
- The strongest baseline is the one with the highest validation F1, fixed by `select` before any test run.
- Test: scenario-stratified sign-flip permutation on the mean paired difference, with a cluster bootstrap 95% CI. Holm at paper level, family as in S1 §2.4.

**Decision rule (W5):**
- CI excludes 0 in our favour after Holm: "outperforms <baseline>".
- CI within ±0.05 F1: "matches".
- CI excludes 0 against us: "<baseline> outperforms".

**Exploratory:** proposed minus every other baseline; per-scenario Δ with 95% CI and W/T/L; recall by evasion strategy.

## Known limits, stated in advance

- **All baselines are our reimplementations or library calls**, configured to emit our ring object. FRAUDAR and Spade were designed for user × object review and transaction graphs, not shared-attribute rings.
- **Spade's latency is not measured.** It is C++ and incremental; ours is Python recomputation, and only Spade's output is reproduced.
- **The GNN is one architecture with fixed training hyperparameters.** A different architecture or a temporal GNN could do better.
- **All data is synthetic**, from the same generator as before.

## Amendments

1. (2026-10-26, process) This protocol's first commit attempt failed silently: `results/r1_*` was gitignored, so the combined `git add` aborted. GraphSAGE and scorer training (seeds 101–110 only) had started about one minute before this file was committed. No tuning (301–303) or evaluation (2101–2120) run had started. Nothing in the design was changed.
2. (2026-10-26, before any evaluation run on 2101–2120) Added one **exploratory** arm, `proposed_const`: the full pipeline with a constant attribute weight. θ_e = 1.0 is the R1 validation selection; θ_a = 0.8; shipped scorer. It was added because R1 (seeds 2001–2010) found the constant at least as good as 1/ln(1+d). Choosing it used R1's test block, so it is tested here on a different block and reported as exploratory, outside the confirmatory family. The confirmatory comparison stays `proposed` (shipped) minus the strongest baseline.
