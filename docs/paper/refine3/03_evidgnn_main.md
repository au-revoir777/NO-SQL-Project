# EvidGNN / EvidPipe: main comparison (H1)

**Protocol:** `docs/research/evidgnn_protocol.md`; amendment 1 is a thread count only.
**Selections:** `results/evidgnn_tuning/selected.json`, committed in 90f892f before any test run.
**Test block:** 4001–4020 × 5 scenarios = 100 paired streams, each block used once.
**Statistics:** scenario-weighted paired differences, 95% cluster bootstrap (10,000), stratified sign-flip.

## Systems (validation-selected)

| System | Selection | Validation F1 |
|---|---|---|
| EvidPipe: shipped detectors + EvidGNN detector (whole graph each batch) + fused scorer (19 ring features + GNN member statistics, out-of-fold) | node threshold 0.9, θ_a 0.3 (θ_a 0.3–0.8 tie) | 0.885 |
| GraphSAGE unscored: strongest existing method (re-selected over the widened grid) | 0.95 | 0.780 |
| GraphSAGE + own scorer | 0.9, θ_a 0.3 | 0.780 |
| Hybrid (W3b) | 0.9, θ_a 0.5 | 0.756 |
| Rules + own scorer | cap 10, cycle, θ_a 0.7 | 0.678 |
| EvidGNN alone (evidence ring rule) | 0.9 | 0.741 |

## Results (4001–4020)

| Method | F1 | P | R | False rings/run | Ring PR AUC |
|---|---|---|---|---|---|
| **EvidPipe** | **0.860** | 0.869 | 0.861 | 1.04 | **0.894** |
| Hybrid | 0.815 | 0.802 | 0.854 | 1.86 | 0.827 |
| Shipped pipeline | 0.763 | 0.787 | 0.760 | 1.48 | 0.824 |
| GraphSAGE unscored | 0.758 | 0.862 | 0.696 | 0.76 | — |
| GraphSAGE + scorer | 0.754 | 0.858 | 0.691 | 0.89 | 0.704 |
| Rules + own scorer | 0.679 | 0.904 | 0.581 | 0.35 | 0.705 |
| EvidGNN alone | 0.651 | 0.737 | 0.604 | 1.44 | — |

Per-scenario F1:

| Method | Adversarial | Baseline | Drift | High noise | Hub heavy |
|---|---|---|---|---|---|
| EvidPipe | 0.652 | 0.990 | 0.947 | 0.771 | 0.942 |
| GraphSAGE unscored | 0.508 | 0.866 | 0.900 | 0.842 | 0.675 |
| Hybrid | 0.634 | 0.953 | 0.750 | 0.839 | 0.898 |
| Shipped pipeline | 0.630 | 0.969 | 0.694 | 0.705 | 0.818 |

### H1 (confirmatory): EvidPipe minus the strongest existing method (GraphSAGE unscored)

- **Overall:** **+0.102** F1, 95% CI [+0.067, +0.138]. Sign-flip p < 0.001 (smallest attainable 5e-5); Holm over four tests stays < 0.001. Win/tie/loss 61/17/22.
- **Per scenario:** adversarial +0.143, baseline +0.124, drift +0.047, **high_noise −0.071**, hub_heavy +0.267.
- **Kill criteria:** the CI excludes 0 in EvidPipe's favour. Per the outcome tree the paper may say "outperforms".

### Exploratory contrasts (same block)

| EvidPipe minus | Δ F1 | 95% CI | p | W/T/L |
|---|---|---|---|---|
| GraphSAGE + scorer | +0.106 | [0.073, 0.140] | < 0.001 | 66/16/18 |
| Hybrid | +0.046 | [0.021, 0.069] | 0.003 | 47/23/30 |
| Shipped pipeline | +0.097 | [0.073, 0.122] | < 0.001 | 62/17/21 |
| Rules + own scorer | +0.182 | [0.154, 0.208] | < 0.001 | 76/19/5 |
| EvidGNN alone | +0.209 | [0.180, 0.238] | < 0.001 | 80/17/3 |

## Reading

- **The gain is a pipeline effect.** EvidGNN alone is the weakest learned method here (0.651). Combined with the pipeline's detectors, tracker and a scorer that uses the GNN's member probabilities, it beats every existing method.
- **The fused scorer's largest coefficient is the mean member GNN probability** (standardised 7.3, against at most 1.3 for any ring feature).
- **Against the hybrid,** which differs in the GNN (gated, evidence edges vs plain GraphSAGE) and in using GNN statistics inside the scorer, EvidPipe gains +0.046. Ablations A5/A6 separate the scorer's part.
- **Where it loses: high_noise** (−0.071 vs GraphSAGE). There the pipeline's candidates include more benign groups and GraphSAGE's node-level threshold is cleaner.
- **On this block the shipped pipeline and GraphSAGE are level** (0.763 vs 0.758). On 2101–2120, GraphSAGE was ahead by 0.059 (W3). The two blocks differ in their draws; both are reported.

## Caveats that stay in the paper

- **Synthetic data only;** labels come from the generator for both GNNs and both scorers.
- **Amount features:** EvidGNN uses transfer-amount features as GraphSAGE does. In round 3, GraphSAGE collapsed when benign and ring amounts overlapped (F1 0.007). The same test on EvidPipe was not declared for this round (block 4701–4710 reserved). It is the first follow-up.
- **Cost:** EvidPipe runs a whole-graph GNN each micro-batch, so it is not incremental. Exact incremental inference was not attempted this round.
