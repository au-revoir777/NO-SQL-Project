# W3b protocol: pipeline + GraphSAGE (hybrid), preregistered

Committed before any hybrid training, tuning or evaluation run.

## Why

In W3 (seeds 2101–2120) GraphSAGE alone outperformed the shipped pipeline: F1 0.778 vs 0.719, Δ −0.059, 95% CI −0.097 to −0.023. The two have complementary strengths:
- **Pipeline:** adaptive rings 24/28 vs 18/28, decoy rings 50/59 vs 37/59, about 9× cheaper per batch.
- **GraphSAGE:** precision, hub-hiding rings.

W3b tests whether adding GraphSAGE to the pipeline outperforms GraphSAGE alone. This design was chosen after seeing W3's test results, so it is tested on a new block.

## Method

- **Hybrid:** the shipped pipeline (pairwise hub-aware detector with θ_e 0.3, temporal cycle, smurfing, ensemble, tracker) plus the W2 GraphSAGE as a fourth detector.
  - GraphSAGE runs on the whole graph every batch, as a full-graph detector, with the same fixed node-to-ring rule.
  - Candidates from all four detectors merge in the existing ensemble; the `n_detectors` feature records agreement.
- **Ring scorer:** logistic regression + isotonic, retrained on the hybrid's own candidates (seeds 101–110 × six training scenarios, node threshold 0.5 during training), same protocol as every other scorer.
- **Tuning:** node threshold ∈ {0.5, 0.7, 0.8, 0.9, 0.95} × θ_a ∈ {0.2, 0.3, 0.5, 0.7, 0.8, 0.9}, on seeds 301–303 × five scenarios. That is 30 points, the proposed method's budget; GraphSAGE alone had 70.

## Evaluation

- **Fresh test seeds 2301–2320** × five accuracy scenarios = 100 paired runs. Never used before.
- Arms on these seeds:
  - `hybrid`;
  - `gnn_unscored` (W2 selection: node threshold 0.95);
  - `gnn` (W2 selection: 0.9, own scorer, θ_a 0.3);
  - `proposed` (shipped).
- Locked environment as in W2.

## Hypotheses

- **Confirmatory (paper family member 3):** hybrid − GraphSAGE alone (`gnn_unscored`, W3's strongest baseline), ring F1, two-sided. Test: stratified sign-flip permutation with a cluster bootstrap 95% CI. Holm at paper level.
- **Exploratory:** hybrid − `gnn` (scored); hybrid − `proposed`; per-scenario Δ; recall by evasion strategy; ms per batch.

## Attribution (rule 10)

Any gain of the hybrid over GraphSAGE alone is attributable to **combining** GraphSAGE with the pipeline's detectors and scorer (an ensemble). It is not evidence for the hub-aware weight or any other single novel element, and will be worded that way. The cost of the hybrid includes GraphSAGE's per-batch whole-graph inference, so it loses the pipeline's cost advantage.

## Decision rule

- CI excludes 0 in favour of the hybrid: "the pipeline with a GraphSAGE detector outperforms GraphSAGE alone by Δ [CI]".
- CI within ±0.05: "matches".
- CI excludes 0 against: "GraphSAGE alone remains best".
