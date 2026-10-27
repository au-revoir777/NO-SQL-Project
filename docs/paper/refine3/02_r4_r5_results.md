# Round 3: R4 (decoys, operating points) and R5 (amount features): results

Protocol: `docs/research/round3_protocol.md`. Everything here is exploratory. The LOSO test is still to come (its GraphSAGE models are not trained yet).

## Decoy sweep (high_noise, seeds 3301–3310, decoys per action 0/1/2/4/8)

Mean F1 over 10 seeds (min–max), and decoy-ring recall:

| Decoys | Proposed | GraphSAGE | GraphSAGE + scorer | Hybrid |
|---|---|---|---|---|
| 0 | 0.70 (0.43–0.86), 19/27 | 0.80 (0.67–1.00), 22/27 | 0.81, 23/27 | 0.85, 24/27 |
| 1 | 0.64, 18/29 | 0.81, 21/29 | 0.80, 22/29 | 0.80, 24/29 |
| 2 | 0.68, 20/28 | 0.86, 23/28 | 0.79, 19/28 | 0.82, 25/28 |
| 4 | 0.68, 20/29 | 0.84, 22/29 | 0.73, 19/29 | 0.79, 23/29 |
| 8 | 0.69 (0.44–0.86), 23/29 | 0.77, 16/29 | 0.72, 18/29 | 0.67, 23/29 |

**Reading.**
- **The proposed pipeline is flat across decoy strength** (0.64–0.70).
- **GraphSAGE falls at 8 decoys** (0.86 at 2 → 0.77 at 8; decoy-ring recall 23/28 → 16/29). At 8 decoys the pipeline finds the most decoy rings, 23/29, tied with the hybrid.
- **At default strength GraphSAGE and the hybrid are ahead.** The paper's sentence "the pipeline finds more decoy rings" (Table V, seeds 2101–2120, all scenarios) does not hold on `high_noise` at default strength.

**Paper wording.** "Under stronger decoy activity GraphSAGE loses decoy-ring recall (from 23/28 to 16/29 between 2 and 8 decoys per action) while the pipeline's stays flat (20/28 to 23/29). At the default strength GraphSAGE finds more."

## Operating points (seeds 3401–3405 × 5; descriptive, swept on test streams)

| Method | Highest recall reached | Precision there | Precision near recall 0.66–0.69 |
|---|---|---|---|
| Proposed (θ_a 0.3–0.9) | 0.78 | 0.64 | 0.88 (θ_a 0.9, R 0.66) |
| GraphSAGE unscored (t 0.8–0.99) | 0.69 | 0.86 | 0.86–0.87 |
| GraphSAGE + scorer (θ_a 0.3–0.9) | 0.69 | 0.88 | 0.88–0.89 |
| Hybrid (θ_a 0.3–0.7) | 0.80 | 0.72 | — (θ_a 0.8/0.9: no alerts) |

**Reading.**
- **At matched recall around 0.66–0.69, precision is the same for all methods** (0.86–0.89).
- **GraphSAGE cannot reach recall above 0.69 at any threshold.** The pipeline and the hybrid reach 0.78–0.80, at the cost of precision.
- **The hybrid's scorer never exceeds 0.8** (calibrated maximum below θ_a), so θ_a 0.8 and 0.9 alert nothing.

## Amount features (R5)

**Ablation (seeds 3501–3520).** The scorer was retrained with amount_mean_log, amount_cv and near_threshold_frac zeroed; their coefficients are 0.
- **Calibrated output tops out at 0.676 without amount features,** so at the shipped θ_a = 0.8 the scorer raises no alert at all. F1 is 0.000 against 0.689: an operating-point artefact, not a measure of ranking.
- **Threshold-free, ring PR AUC drops from 0.769 to 0.551,** and precision at 10 from 0.469 to 0.410.
- **The scorer does depend on transfer-size features.** By the protocol's rule this goes into the abstract's precision sentence.

**Overlapping amounts (seeds 3601–3610; benign median 120 → 2,000; every model trained on the default generator).**

| Arm | F1 | Precision | Recall | Ring PR AUC |
|---|---|---|---|---|
| Pipeline (all features) | 0.535 | 0.463 | 0.720 | 0.656 |
| Pipeline, no amount features | 0.000 (no alerts) | — | 0 | 0.490 |
| Rules + own scorer | 0.642 | 0.822 | 0.564 | 0.646 |
| GraphSAGE | 0.007 | 0.125 | 0.004 | — |

**Reading.**
- **When benign amounts overlap with ring amounts, the pipeline keeps its recall (0.72) but loses precision** (0.69 on the default generator, seeds 3501–3520, to 0.46).
- **GraphSAGE collapses** (F1 0.007): its node features include transfer amounts, and the shift moves benign accounts out of its training distribution.
- **The rules with their own scorer degrade least.**
- **This is the strongest robustness result against GraphSAGE so far.** It also applies to any GNN that uses amount features, EvidGNN included (16 features, 12 shared with GraphSAGE). EvidGNN's overlap block (4701–4710) was declared "not used this round". Running it would need a protocol amendment before the run.

Pipeline minus GraphSAGE under overlap: +0.528 [0.493, 0.562]. Pipeline minus rules: −0.108 [−0.156, −0.058].
