# EvidGNN: design (S1), protocol (S2), ablations and kill criteria (S3)

Committed before any EvidGNN model is trained on the training seeds, and before any tuning or test run. Code: `src/fraudsim/detectors/evidgnn.py`, `src/fraudsim/experiments/evidgnn.py`. Stage 0A/0B (literature and datasets) are in `docs/research/gnn/`. Amendments are appended with reasons.

**Goal (user, 2026-10-27):** a GNN-inclusive pipeline that beats every existing method on this benchmark, including the GraphSAGE baseline, under the paper's evidence rules.

## S0C. The GraphSAGE baseline being beaten (audited from the code)

| Item | Value |
|---|---|
| Layers / hidden / aggregator | 2 / 64 / mean (`detectors/external.py::make_sage`) |
| Neighbour selection | **full neighbourhood, no sampling.** A hub node aggregates all its users, so there is no degree cap; a 50-user hub mixes everyone |
| Graph | users and attributes as nodes; user–attribute links (both directions); user–user transfers in the 900 s window |
| Features | 12: link counts per kind, transfer counts and amounts in/out, account age, node-type flags, attribute kind and log degree |
| Loss | BCE with positive-class weight (negatives/positives), Adam lr 0.005, weight decay 5e-4, dropout 0.2, 40 epochs, seed 0 |
| Training set | 879 whole-graph snapshots (every 5 s) from seeds 101–110 × six scenarios; 322,814 user rows, 10,821 positive (3.4%); 18.6 min on CPU |
| Node-to-ring rule | connected components over **any** shared attribute or transfer among flagged users, kept at size 3–25 |
| Tuning | 70 grid points on 301–303: node threshold 10 values unscored, and 10 × 6 alert thresholds scored. Selected unscored threshold **0.95 is the grid's top edge**, and F1 was still rising (0.9: 0.775, 0.95: 0.780) |
| Test (2101–2120) | F1 0.778 unscored; 0.751 with own scorer |

Fairness fix before the test: GraphSAGE's unscored grid is widened upward ({0.97, 0.98, 0.99, 0.995}) on 301–303. Its selection is then re-made.

## S1. Design

### Gated graph (per micro-batch, whole active graph)
- **R1 user–attribute:** only for attributes with degree ≤ 27 (the solo-link cutoff of h = 1/ln(1+d) at θ_e 0.3). **Gate:** a busy attribute is not a message-passing node.
- **R2 user–user transfers** in the window.
- **R3 user–user evidence edges:** pairs with W(u,v) ≥ θ_e (0.3) and a non-zero attribute term. W is the pipeline's evidence (1/ln weights, 300 s decay, β 0.15, β_max 0.6). Candidate pairs come only from non-busy shared attributes and transfers, so a busy attribute contributes to W only as support: it never links a pair alone.
- **Evidence-aware neighbour selection:** each user keeps its top-16 R3 edges by W (deterministic, ties broken by id).
- **Known gap:** a pair whose only link is two or more busy attributes is never formed. This is the same as the engine's fan-out mode; it is documented, not repaired.

### Model
- **Features:** 16 = the baseline's 12, plus the user's evidence degree, sum of W, max W, and number of busy attributes held.
- **Layers:** two layers of relation-aware SAGE, h' = ReLU(W_s h + Σ_r W_r · mean_r(h)), with a W-weighted mean on R3; hidden 64, dropout 0.2. L = 2 matches the baseline and the engine's k = 2 region.
- **Training:** identical to the baseline (loss, optimiser, epochs, seed, snapshots, labels).

### Ring rules
- **"evidence":** connected components of R3 among flagged users, peeled to density ≥ 0.75 and size 3–25 (the pipeline's peel).
- **"any":** the baseline's rule. Both rules are run for both models (ablations) so the gain can be attributed.

### EvidPipe (the GNN-inclusive pipeline)
- **Detectors:** the shipped pipeline's detectors (pairwise hub-aware, temporal cycle, smurfing) plus the EvidGNN detector, in one ensemble and tracker. EvidGNN runs on the whole graph every batch.
- **Scoring:** a fused ring scorer, logistic regression + isotonic calibration over the 19 ring features plus three GNN member statistics (mean and minimum node probability, fraction of members flagged).
- **Stacking without leakage:** the scorer is trained on seeds 101–110 with out-of-fold GNN scores. Seeds 101–105 are scored by a GNN trained on 106–110, and vice versa. At test time the GNN trained on all of 101–110 is used.

### Not attempted in this round
- **Exact incremental inference** (component 2): the main and hub runs use whole-graph inference per batch.
- **Pseudo-label training** (component 3) is exploratory only (see H4).
- **The optional evidence-restricted ring scorer.**

The reason is scope: the user's goal is accuracy against existing methods. Component 2 stays planned (S4).

## S2. Protocol

### Seeds (fresh, declared, each block used once)
- **Training:** 101–110 (as every baseline).
- **Validation:** 301–303 (as every baseline). Block 311–320 stays reserved and unused, so validation is identical for all methods.
- **Main comparison:** 4001–4020 × 5 scenarios (100 paired streams).
- **Ablations:** 4101–4120 × 5.
- **Label efficiency:** 4301–4310 × 5 (subsampling seed 7001).
- **Leave-one-scenario-out:** 4401–4420 (20 per left-out scenario).
- **Hub-size sweep:** 4201–4205 / 4211–4215 / 4221–4225 (500 / 2,000 / 10,000-account hub), ranges only.
- **Not used this round:** 4501–4505 (exactness/latency), 4601–4620 (decoy), 4701–4710 (amount overlap), 8001–8005 (initialisation seeds).

### Tuning (validation 301–303 × 5 scenarios)
- **EvidGNN alone:** node threshold ∈ {0.5, 0.7, 0.8, 0.9, 0.95}.
- **EvidPipe:** node threshold {0.5, 0.7, 0.8, 0.9, 0.95} × θ_a {0.3, 0.5, 0.7, 0.8, 0.9}.
- **Budget:** 30 points, against GraphSAGE's 70 + 4. Selection: maximum mean ring F1, ties to the lower threshold. Edge selections are reported, not widened after test results are seen.

### Methods on the main block
- EvidPipe and EvidGNN alone (selected configurations).
- GraphSAGE unscored (re-selected after widening) and GraphSAGE + own scorer (W2 selection).
- The hybrid (W2/W3b selection), the shipped pipeline, and the rules with their own scorer (W2 selection).

### Confirmatory family (Holm over four, declared now)
- **H1 (main, 4001–4020):** F1(EvidPipe) − F1(strongest existing method) > 0. The strongest existing method is whichever of GraphSAGE unscored / GraphSAGE + scorer / rules + own scorer has the highest validation F1 after re-selection. Paired, scenario-weighted, 95% cluster bootstrap, stratified sign-flip.
- **H2 (ablations, 4101–4120):** F1(EvidGNN, gate on) − F1(EvidGNN, gate off), both with the evidence ring rule, the same tuning, and the same training.
- **H3 (LOSO, 4401–4420):** for EvidGNN alone vs GraphSAGE alone (both unscored, at their selected thresholds), the F1 drop when the test scenario is left out of training is smaller for EvidGNN. Test: paired difference of drops by stream. GraphSAGE's LOSO models come from round 3 (`results/round3_gnn`), trained identically.
- **H4 (label efficiency, 4301–4310):** at a 10% label budget (snapshots subsampled with seed 7001), F1(EvidGNN alone) − F1(GraphSAGE alone) > 0, both retrained on the same subsample.

**Effect sizes.** The smallest difference worth reporting is 0.03 F1. Equivalence uses ±0.05 on the 90% interval.

**Everything else is exploratory:** the ring-rule swaps, hub-size sweep, scored variants, pseudo-labels, per-scenario results.

## S3. Ablations and kill criteria

### Ablations (block 4101–4120 × 5)

| ID | Variant | Tests |
|---|---|---|
| A0 | EvidGNN, gate on, evidence ring rule | reference |
| A1 | Gate off (busy attributes pass messages; no R3), evidence ring rule | value of the gate (H2) |
| A2 | Gate on, "any" ring rule | value of the evidence ring rule |
| A3 | GraphSAGE baseline, evidence ring rule | ring rule without the gated model |
| A4 | GraphSAGE baseline, "any" rule (its own) | reference baseline |
| A5 | EvidPipe | full system |
| A6 | EvidPipe, shipped 19-feature scorer instead of fused | value of fusing GNN statistics |

Gate off still keeps user–attribute links for every attribute, including busy ones. A3 vs A4 and A0 vs A2 separate the ring rule from the model.

### Kill criteria (declared now)
- **Gate:** drop the gate claim if A1 is within ±0.02 F1 of A0 overall and on `hub_heavy`.
- **Evidence ring rule:** drop it if A2 is within ±0.02 of A0 and A3 is within ±0.02 of A4.
- **Fusion:** drop it if A6 is within ±0.02 of A5.
- **Main claim:** if H1's CI includes 0, the paper may only say "matches"; if the CI lies within ±0.05, "is equivalent to"; if it excludes 0 against EvidPipe, "does not beat GraphSAGE". In no case "outperforms".

### Outcome tree (abstract sentence per outcome)
- **H1 positive, gate helps:** "An evidence-gated GNN inside the pipeline outperforms the strongest existing method by Δ (CI); removing the gate costs Δ₂."
- **H1 positive, gate does not help:** "The gain comes from combining a GNN with the pipeline's evidence (ring rule and fused scorer), not from gating message passing."
- **H1 null:** "Adding an evidence-gated GNN matches but does not beat GraphSAGE; the pipeline's contribution is robustness (adaptive and decoy rings) and evidence-based rings, not accuracy."
- **H3 favours EvidGNN:** "The gated model loses less when a scenario is unseen." Otherwise: "Both models depend on having seen the scenario."
- **GraphSAGE wins everywhere:** a complementarity and negative result. The paper keeps the evidence condition as its contribution and reports that a GNN trained on generator labels is the stronger detector on synthetic data.

## Amendment 1 (2026-10-27, before any model was saved or any tuning run)
PyTorch's default of two intra-op threads on this two-core container, with other jobs running, made one training step about 250 times slower (1.08 s vs 4.3 ms on the same snapshot; the first training run was stopped by the time limit at epoch 1). EvidGNN training and inference are therefore fixed to one thread (`torch.set_num_threads(1)`). This changes speed only; floating-point reduction order can differ in the last bits. Training also now caches snapshots on disk and checkpoints every epoch. The GraphSAGE baseline is unchanged (its saved model and recorded results stay as they are).

## Amendment 2 (2026-10-27, after the main, ablation and H4 blocks; before any run of what follows)

**Why.** The ablations show the gate and the evidence ring rule hurt. The fused ring scorer is what makes the GNN-inclusive pipeline work. The gated model is also a weaker node classifier than GraphSAGE (A2 − A4 = −0.058). The simpler candidate is therefore the pipeline fused with **plain GraphSAGE**. These blocks have been seen, so it is tested only on fresh blocks. Everything in this amendment is **exploratory** and outside the confirmatory family of four.

**System "SagePipe".**
- **Detectors:** the shipped detectors plus the GraphSAGE detector (W2 model, whole graph each batch, as in the hybrid).
- **Scorer:** the fused scorer over the 19 ring features plus GraphSAGE member statistics (mean and min probability, fraction flagged), trained on 101–110 with out-of-fold GraphSAGE scores.
- **Fold models:** GraphSAGE trained on 101–105 and on 106–110, with the W2 settings (one thread).
- **At test time:** the W2 GraphSAGE model (trained on 101–110).

**Tuning.** On 301–303 × 5: node threshold {0.5, 0.7, 0.8, 0.9, 0.95} × θ_a {0.3, 0.5, 0.7, 0.8, 0.9}, with the same selection rule as EvidPipe. The selection is committed before the test.

**Blocks (fresh; not used before).**
- **4801–4820 × 5 (comparison):** SagePipe, EvidPipe, GraphSAGE unscored, hybrid and shipped pipeline at their committed selections. Report SagePipe − GraphSAGE, EvidPipe − GraphSAGE and SagePipe − EvidPipe.
- **4701–4710 × 5 (amount overlap):** scenario override `simulation.amount_median = 2000`, all models trained on the default generator. Arms: EvidPipe, SagePipe, GraphSAGE unscored, shipped pipeline, rules + own scorer.

**Reporting.** Paired differences with 95% CIs and uncorrected p-values, labelled exploratory. If SagePipe is within ±0.05 of EvidPipe (90% CI), the paper presents the simpler system (any GNN + fused scorer) as the method, and EvidGNN's gate as a tested and rejected design.

## Amendment 3 (2026-10-27, after the hub-size sweep at 500 and 2,000 for the four declared arms; before any SagePipe hub run)

**What prompted it.** In the exploratory hub-size sweep, EvidPipe flags 58 (500-account hub) and 89 (2,000-account hub) false rings per run. Its F1 falls to 0.10–0.23. GraphSAGE, the hybrid and the shipped pipeline stay at 0.75–1.00. Training hubs are at most about 80 accounts, so this is a second shift weakness besides transfer amounts.

**Added, exploratory, ranges only.**
1. **SagePipe on the same hub blocks** (4201–4205, 4211–4215). This reuses blocks seen for other arms, so it is labelled "same seeds, added after".
2. **Per-detector origin of EvidPipe's false rings** on 4201–4203: which detector proposed each alerted false ring, and its fused-scorer inputs. This is a diagnosis, not a test.

The 10,000-account size is run only for arms that are not collapsed at 2,000.

*Correction to amendment 3 (same day).* "Training hubs are at most about 80 accounts" was an estimate. Measured on the training snapshots, the largest attribute degree is 176 (`scale_sweep`). It is at most 75 in the other five scenarios (`docs/research/gnn/` cache, no-gate graphs). The 500–10,000 hubs are still outside the training range.
