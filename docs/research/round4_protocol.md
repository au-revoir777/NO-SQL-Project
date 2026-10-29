# Round 4 protocol (I2.2, I2.5, I3)

Committed before any code for these runs and before any run on the blocks below. All seed blocks are fresh: no block at or above 6001 exists in `results/`. Locked environment. One PyTorch thread (as in evidgnn amendment 1). Statistics are as elsewhere: scenario-weighted paired differences, 95% cluster bootstrap, stratified sign-flip. Equivalence is claimed at ±0.05 and also reported at ±0.03 (I2.7). Results on five or fewer seeds are reported as ranges.

## I2.2 Hub condition: tuned control (no new run)

- **N-D design.** In N-D (followups_protocol.md) the preregistered primary was `log_two` − `log_one`; it is the null result. `const_two` − `const_one` was a declared *secondary* contrast. Its "can suffice" arm used θ_e = 0.5.
- **Whether a tuned control is needed.** On validation 301–303 (`results/r1_tuning/selected.json`), the constant weight gives the same mean F1 (0.5693) at every θ_e from 0.1 to 0.8. Every θ_e < 1 lets one attribute link a pair, and the choice of value inside that range does not change validation F1.
- **Decision.** A tuned "can suffice" arm would be any θ_e in 0.1–0.8; θ_e = 0.5 is already one of them. No new run. The paper states this and labels the +0.137 contrast secondary.

## I2.5 A fraud-specific GNN baseline: BWGNN

**Model.** BWGNN (Tang et al., ICML 2022), homogeneous version, re-implemented in PyTorch from the authors' code (github.com/squareRoot3/Rethinking-Anomaly-Detection, `BWGNN.py`):
- MLP(in → 64 → 64, ReLU);
- C + 1 = 3 Beta-wavelet polynomial filters of order C = 2 on the symmetric normalised Laplacian of the undirected graph (thetas from `calculate_theta2`);
- concatenation, then Linear(3·64 → 64), ReLU, Linear(64 → 1);
- Adam at lr 0.01 and class-weighted BCE (the authors' defaults); 100 epochs (the authors' maximum; their early stopping is not used, so no validation labels enter training).

**Graph and labels.** The GraphSAGE baseline's graph, 12 node features, snapshots and labels (seeds 101–110 × six scenarios, every 5 s).

**Node-to-ring rule.** GraphSAGE's ("any" shared attribute or transfer among flagged users, components of size 3–25).

**Tuning.** On 301–303 × 5, node threshold ∈ {0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.97, 0.98, 0.99, 0.995}, the same grid as GraphSAGE after widening. The selection is committed before the test.

**Test block 6001–6020 × 5 (100 paired streams).**
- **Arms:** BWGNN, GraphSAGE (0.95), AnchorPipe (committed selection), shipped pipeline.
- **Exploratory contrasts:** AnchorPipe − BWGNN and BWGNN − GraphSAGE.
- **Wording by outcome:**
  - **AnchorPipe − BWGNN CI excludes 0 (positive):** "AnchorPipe also beats a fraud-specific spectral GNN (BWGNN)."
  - **CI includes 0:** "AnchorPipe matches BWGNN."
  - **CI excludes 0 (negative):** "BWGNN is ahead"; the superiority claim is limited to GraphSAGE.
  - **BWGNN ahead of GraphSAGE:** BWGNN becomes the strongest tested method, and every "strongest" sentence is updated.

## I3 Guard controls

**Triggers.** All run inside AnchorPipe with its committed thresholds and scorers; only the trigger changes. Each trigger fires when its statistic exceeds the 99.5th percentile of that statistic on unlabelled hold-out streams 201–205 × 6 (the same reference as the shipped guard, recomputed per trigger before any test run).

| ID | Trigger statistic |
|---|---|
| G-flag | Shipped guard: median over 5 batches of the share of active users with GNN p ≥ 0.5 |
| G-amount | Two-sample Kolmogorov–Smirnov D between the transfer amounts of the last 200 transfers and a pooled reference sample of hold-out transfer amounts (an input-drift test) |
| G-score | KS D between the GNN scores of active users in the current batch and a pooled reference sample of hold-out GNN scores (an output-drift test, as in BBSD) |
| Never | Never fires (= AnchorPipe without guard) |
| Always | Always fires (GNN detector candidates, scored by the rule scorer) |
| Oracle | Post hoc, per stream, the better of Never and Always (an upper bound for any whole-stream trigger) |

**Shift blocks** (fresh; five accuracy scenarios × 5 seeds unless stated; every model trained on the default generator):

| ID | Seeds | Shift | Override |
|---|---|---|---|
| S0 | 6101–6105 | none (false-trigger rate) | — |
| S1 | 6111–6115 | transfer-amount overlap | `simulation.amount_median` 2000 |
| S2 | 6121–6125 | event rate | `simulation.target_event_rate` 30 |
| S3 | 6131–6135 | heavier activity tail | `simulation.heavy_tail_alpha` 1.3 |
| S4 | 6141–6145 (hub_heavy only) | hub-size distribution | 2,000-account office hub (`large_hubs.overrides(2000)`) |
| S5 | 6151–6155 | ring size | `random_rings.size_min` 8, `size_max` 12 (scenarios with random rings) |
| S6 | 6161–6165 | ring amounts benign-like (aimed at changing GNN errors without changing its flag rate) | `simulation.evasion_params.<mode>.amount_mult` 0.1 for every evasion mode |

**Methods per stream.**
- AnchorPipe with G-flag, G-amount, G-score, Never and Always.
- References: GraphSAGE, shipped pipeline, rules + own scorer.

**Metrics.**
- F1 per shift.
- False triggers: share of S0 streams in which the trigger fired at least once, and share of S0 batches.
- Detection delay: simulated seconds from stream start to first firing; shifts start at t = 0.
- F1 cost of a late trigger: F1(trigger) − F1(Always) on streams where Always beats Never.

**Decision rules.**
1. If G-amount or G-score has F1 within ±0.03 of G-flag on S1, and no more S0 false triggers, the contribution is described as "a fallback pattern; a standard input- or output-drift test serves as the trigger as well as ours". The abstract says so.
2. If G-flag is better than both standard triggers on S1 (CI excludes 0) without more false triggers, the flag-rate trigger is reported as the better trigger in this setting.
3. For any shift where Never is better than Always, a trigger that fires costs F1, and the claim becomes "the guard helps under transfer-amount shift; under shifts X it should stay off".
4. Blind spot: if on S6 the GNN pipeline loses F1 against the rule pipeline and G-flag does not fire, this is reported as the guard's stated blind spot.

**Wording.** "Survives shift" becomes "survives a transfer-amount shift" unless I3 shows the guard helps under other shifts.

**All of I3 is exploratory.**
