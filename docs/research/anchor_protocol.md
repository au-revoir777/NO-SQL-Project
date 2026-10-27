# AnchorPipe: evidence-anchored, shift-guarded GNN fusion (protocol)

This protocol was committed before any AnchorPipe code ran on any stream, and before any run on the blocks below. Amendments are appended with reasons.

**Motivation.** Results so far (`docs/paper/refine3/`):
- The GNN-inclusive pipeline (SagePipe/EvidPipe) beats every existing method in distribution, by about +0.09 F1 over GraphSAGE on three blocks.
- It fails under shift. With overlapping amounts its F1 is 0.40–0.45, against 0.64–0.66 for the rule-based pipeline and the rules. EvidPipe collapses at large hubs. GraphSAGE alone loses 0.057 on an unseen scenario.
- The user's goal is a GNN-inclusive pipeline that beats existing methods, with novelty.

**Idea.** The pipeline's pairwise evidence is label-free and stable under these shifts; the GNN is accurate but brittle. Use the evidence to check the GNN in two places.

1. **Local: evidence anchoring.**
   - A member's GNN probability counts towards its ring's score only if the member is *anchored*. Anchored means it has at least one pairwise-evidence edge (W ≥ θ_e, the pipeline's rule: no busy attribute alone) to another member of the same candidate ring.
   - The ring scorer receives `anch_mean_p` (mean of p·anchored) and `anch_frac` (fraction anchored), in addition to SagePipe's `gnn_mean_p`, `gnn_min_p` and `gnn_frac_flagged` and the 19 ring features.
   - Hypothesis: benign groups that the GNN inflates under shift (large co-users of a hub, large benign transfers) are rarely evidence-anchored.
2. **Global: label-free shift guard.**
   - Each micro-batch, s_t is the fraction of active users with GNN probability ≥ 0.5. The guard statistic g_t is the median of s over the last K = 5 scored batches.
   - The reference distribution of g comes from the scorer hold-out seeds **201–205** × six scenarios. These are labelled, but the labels are not used: the statistic is computed on unlabelled GNN outputs.
   - The guard fires while g_t > q_{0.995}(reference). While it fires, the ring is scored by the shipped 19-feature scorer. Its risk r_s is mapped monotonically onto the fused scale, so that alerting at θ_a(fused) equals alerting r_s at θ_a(shipped):
     - r' = θ_f · r_s / θ_s if r_s < θ_s;
     - r' = θ_f + (1 − θ_f)(r_s − θ_s)/(1 − θ_s) otherwise.
   - Hypothesis: under amount or hub-size shift, the GNN flags far more of the population than it ever does in distribution.

**GNN.** The W2 GraphSAGE (no gate; SagePipe showed the gate is unnecessary), used as a whole-graph detector each batch, as in SagePipe.

**Scorer training.** Seeds 101–110, out-of-fold GraphSAGE scores (fold models `results/evidgnn/graphsage_{A,B}.pt`, as SagePipe), with the same fit/calibration split. The guard is off during training.

**Development (label-aware checks only on development data).**
- **Data:** validation 301–303 × 5 (in distribution), plus *development shifts* on fresh development seeds 5001–5005:
  - amount median 1,000 (× 5 scenarios);
  - hub_heavy with a 300-account hub.
- **Tuning:** node threshold {0.5, 0.7, 0.8, 0.9, 0.95} × θ_a {0.3, 0.5, 0.7, 0.8, 0.9}, selected on validation 301–303 only (as SagePipe).
- **Allowed guard change:** if the guard fires on more than 10% of validation batches, or never fires on a development shift, K or the quantile may be changed **once** (recorded as an amendment) before any test block. Nothing else is tuned on development shifts.

**Test blocks (fresh, each used once; seeds never used before in this repository).**

| Block | Condition | Streams |
|---|---|---|
| T1: 5101–5120 × 5 scenarios | In distribution | 100 |
| T2: 5201–5210 × 5 | Amount overlap (benign median 2,000, as before) | 50 |
| T3: 5301–5310 × 5 | Stronger amount shift (benign median 5,000; not seen in development) | 50 |
| T4: 5401–5405 (500) and 5411–5415 (2,000) | hub_heavy, large office hub | 10, ranges |

**Methods on every block.**
- AnchorPipe.
- Ablations:
  - AnchorPipe without the guard ("anchor only");
  - AnchorPipe without the anchoring features but with the guard ("guard only").
- SagePipe.
- GraphSAGE unscored (selected 0.95).
- Shipped pipeline.
- Rules + own scorer.
- Hybrid.

All use their committed selections.

**Confirmatory family (Holm over three; scenario-weighted paired differences, 95% cluster bootstrap, stratified sign-flip).**

| ID | Hypothesis | Block |
|---|---|---|
| A1 | F1(AnchorPipe) − F1(GraphSAGE) > 0 | T1 |
| A2 | F1(AnchorPipe) − F1(SagePipe) > 0 | T2 |
| A3 | Non-inferiority: F1(AnchorPipe) − max(F1(shipped pipeline), F1(rules)) has a 90% CI lower bound > −0.05 | T2; per stream, the better of the two by its block mean |

**Exploratory:**
- T3 and T4 results;
- the ablations;
- AnchorPipe − SagePipe on T1 (the price of the guard and anchoring in distribution);
- how often the guard fires.

**Outcome wording.**
- **All three supported:** "Anchoring a GNN in label-free pairwise evidence keeps its in-distribution gain and removes its failure under shift."
- **A1 holds, A2 or A3 fails:** "The guard and anchoring do not repair the shift failure." Report the shift results honestly.
- **A1 fails:** "Anchoring costs the in-distribution gain."

## Development check (5001–5005), before any test block

| Shift | Guard fallbacks | AnchorPipe | Anchor only | SagePipe | Shipped pipeline |
|---|---|---|---|---|---|
| Amount median 1,000 | 2,963 | **0.638** | 0.403 | 0.447 | 0.649 |
| 300-account hub (hub_heavy) | 0 | 0.907 | 0.907 | 0.894 | 0.804 |

- **The guard did not fire on the 300-account hub,** which formally permits the one allowed change.
- **No change is made.** The GNN does not fail at this hub size (SagePipe 0.894), so there is nothing for the guard to catch.
- **The guard stays as declared:** K = 5, q = 0.995, τ = 0.456.
- **The guard never fired on validation.**
- **Anchoring alone does not repair the amount shift** (0.403). The scorer gives the anchoring features near-zero weight (−0.42 and +0.02 against +5.9 for the GNN mean probability).

Selections are now locked (`results/anchor/selected.json`).
