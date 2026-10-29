# Round 4: input check and I1 (novelty audit)

## Input check

**Received or read directly**
- Revised paper: PDF (19 pages) and full LaTeX source.
- Result CSVs and every block under `results/`.
- Scenario YAMLs (`configs/scenarios/`).
- Code (`src/fraudsim`, `scripts/`).
- `REPRODUCE.md`, the `docs/research/` protocols and `PROTOCOL_LOG.md`.
- Web search was available. The prior-art statements below come from searches run for this audit (listed at the end) and from the Stage 0A literature file `docs/research/gnn/s0a_related_work.md`, which lists 69 screened and 23 read papers.

**Cannot verify**
- Whether the Windows-era tables (III, IX, X) reproduce on Linux; this is not rerun here (I5).
- The full text of the 2025–2026 citations (I6).
- Any production or real-data behaviour: all evidence is synthetic.

## Audit table

| | (a) Keep hub links, but never let a hub link a pair alone | (b) Shift-guarded GNN pipeline (AnchorPipe) |
|---|---|---|
| **Claim sentence** | We show that inside a streaming ring detector, capping busy shared attributes costs ring F1 even when the cap removes only attributes that cannot link a pair alone (−0.051 at cap 27). Busy attributes help as corroborating evidence. Prior work Y does not test this because it either keeps the weight and never isolates the cap (FRAUDAR, Spade) or applies block purging as a default (meta-blocking). Z: the isolation controls. | We show that rule candidates scored with a GNN's member probabilities (stacking) beat GraphSAGE in distribution (+0.099). We also show that a label-free trigger on the GNN's flag rate, falling back to the rule scorer, keeps rule-level F1 under a transfer-amount shift where the GNN pipeline loses 0.239. Prior work Y does not combine these inside a streaming ring detector. Z: A1–A3 and the guard-only and anchor-only ablations. |
| **Closest prior work (searched, VERIFY)** | **Meta-blocking (Papadakis et al., TKDE 2014):** ARCS sums inverse block cardinalities; ECBS discounts entities in many blocks; weighted edge pruning drops edges below a threshold; block purging discards oversized blocks. This is the same structure as W = Σ h(d) + threshold θ_e, with the cap as block purging. Also: Adamic–Adar (1/log degree of shared neighbours); FRAUDAR column weight 1/log(x+c), c = 5; Spade (the same weight, incremental and exact); PromoGuardian (edges only when two relations co-occur). | **Failing Loudly (Rabanser et al., NeurIPS 2019):** shift detection on a model's outputs (BBSD) works best in their study. **BBSE (Lipton et al., ICML 2018):** shift is estimated from the predicted label distribution. Also: selective prediction and abstention (for example arXiv 2505.15008); stacked generalisation (Wolpert 1992, VERIFY: not opened); industrial drift-triggered model updates (US patent 12346781, VERIFY: not read in full). |
| **New vs applied** | Applied: the weighting, the threshold and the purging are all known. New: the empirical finding, under isolation, that purging busy blocks hurts here even when they cannot link alone, and that a step weight with the same solo-link cutoff loses 0.041. I found no fraud or ER paper that tests purging only the blocks that cannot form an edge alone. | Applied: out-of-fold stacking, an output-distribution shift statistic and a rule fallback. New: the arrangement and its evaluation on fresh blocks. The trigger statistic (share of users with p ≥ 0.5) is a one-dimensional BBSD/BBSE statistic. I found no paper that uses a GNN's flag rate to switch a ring scorer to a label-free evidence scorer. That is a narrow application gap, not a mechanism. |
| **Reviewer's dismissal** | "This is meta-blocking's ARCS weighting with weighted edge pruning, and the cap you beat is block purging." | "This is stacking plus a drift-triggered fallback to the rules." |
| **Answer from the controls** | Partly answered. Cap 10 (−0.08, Holm p = 0.007) and cap 27 (−0.051, exploratory) show that purging hurts in this setting; meta-blocking papers do not test purging in isolation in fraud streams (unsearched beyond the survey, VERIFY). The weighting itself has no answer: it is not ours. | Not answered yet. The guard is compared only with "no guard". If a standard drift test on amounts or on the score distribution does as well, the contribution is "a fallback pattern" (I3). Stacking is supported as the source of the in-distribution gain (fused − shipped scorer +0.101; hybrid without GNN statistics 0.097 below SagePipe). |
| **Six-part test** | 1 ✓; 2 ✗ (a parameter regime of known weighting and pruning); 3 ✓ (cap control confirmatory; cap 27 exploratory); 4 ✓ (cap 27 was the falsifier and did not falsify); 5 ✓; 6 partly | 1 ✓; 2 ✗ (arrangement of known components); 3 partly (guard and anchoring removed; no standard-trigger control); 4 ✓ (A2/A3 declared); 5 ✓; 6 ✗ pending I3 |
| **Verdict** | **Not novel as a mechanism; an incremental, isolation-tested empirical finding** | **Incremental (system plus evaluation); not novel as a mechanism** |

## Where the defensible novelty sits

**Your view stands, with one correction.** Both contributions are incremental. The protocol is good practice, not a contribution: committed protocols and Holm families are standard. Present it as rigour, not novelty.

**Defensible value:**
1. **Isolation-tested findings with falsifiers that were run:**
   - Busy attributes act as corroborating evidence (the cap-27 result).
   - The discount's shape matters at the margin (step −0.041).
   - A GNN's lead depends on seen scenarios (LOSO drop 0.057 vs 0.001) and on training-like amounts (GraphSAGE F1 0.000 under overlap).
   - Stacking GNN member probabilities into rule candidates is what beats GraphSAGE (+0.101 over the shipped scorer, three blocks).
2. **Rejected designs, reported as such:** the message-passing gate (−0.063, confirmatory) and evidence anchoring (+0.009, CI touches 0).
3. **A label-free flag-rate trigger** that separates transfer-amount shift from in-distribution data in this generator. It fires on every shifted stream and never in distribution. It has not been compared with standard drift tests (I3).

**What the current abstract claims beyond this:**
- **"Learned graph models are more accurate but brittle."** Partly supported. Without stacking, GraphSAGE is ahead of the pipeline on one block, level on one, and +0.04 on another.
- **"A label-free shift guard"** is presented as the design point, with no comparison to standard shift detection.
- **"Beats the strongest existing method."** It beats the strongest *tested* method; no fraud-specific GNN was tested.
- **"Streaming pipeline"** while AnchorPipe recomputes the GNN on the whole graph each batch, with no cost given (240 s vs 11 s at 10,000 accounts).
- **The source of the win (stacking) is not named.**
- **"Stays level" under shift** holds for a transfer-amount shift only.

## Alternative framings the evidence supports

**(a) Hub links**
- **a1. Empirical study.** "Degree caps in streaming fraud-ring detection: an isolation study." Caps cost F1 even when they remove only attributes that cannot link alone; busy attributes are corroborating evidence.
- **a2. Transfer from entity resolution.** Meta-blocking-style weighting and pruning applied to fraud rings, with the finding that block purging (the cap) is harmful in this setting.

**(b) GNN pipeline**
- **b1. Engineering result.** "When to trust a fraud GNN": stacking GNN member probabilities on rule candidates beats GraphSAGE in distribution, and an output-rate trigger with rule fallback contains the damage of a transfer-amount shift.
- **b2. Robustness and diagnosis.** A GNN's advantage on synthetic fraud-ring detection depends on seen scenarios and training-like amounts; a simple label-free fallback recovers the rule pipeline's level.

## Title

"Shift-Guarded GNN" is exposed: the guard is unproven against standard triggers and was tested on amount shifts only. "Streaming" is exposed for AnchorPipe. Options:
1. **"Keeping Hub Links: Pairwise Evidence, GNN Stacking and a Rule Fallback for Fraud Ring Detection"** (drops both exposed words).
2. **"When Does a GNN Help Fraud-Ring Detection? Hub Links, Stacking and a Fallback under Shift"** (empirical-study framing).
3. Keep "Streaming" only if the title names the shipped pipeline; the GNN arm must then be described as whole-graph.

## Claims ledger (first version)

| # | Claim | Type | Evidence | Strongest comparator | Attributable to | Status | Allowed wording |
|---|---|---|---|---|---|---|---|
| L1 | A degree cap inside the pipeline costs ring F1 | mechanism | Table VI, 2001–2010, confirmatory (Holm p 0.007) | pipeline with cap 10 | keeping hub links | supported | "In our simulator, a cap of 10 inside the pipeline costs 0.08 ring F1 (Holm p = 0.007)." |
| L2 | Even cap 27 (busy attributes only) costs F1 | mechanism | 3001–3020, exploratory | cap 27 | busy attributes as corroborating evidence | supported (exploratory) | "…costs 0.051 (exploratory)." |
| L3 | The condition "no busy attribute links alone" is what matters | mechanism | N-D 2401–2420: "rare cannot suffice" confirmatory null (0.000, p 0.98); "hub cannot suffice vs can" +0.137 exploratory, can-arm at θ_e 0.5 vs selected 1.0 | constant weight, θ_e 0.5 | hub condition (untuned control) | partly | "Letting one busy attribute link a pair alone cost 0.14 in an exploratory, untuned comparison." Needs a tuned control (I2.2). |
| L4 | Given the condition, the shape does not matter | mechanism | 2401–2420: 1/ln vs constant −0.008 [−0.020, 0.003], exploratory; step weight −0.041 [−0.061, −0.021] | step weight | — | partly | "Two of the three weights that meet the condition were equivalent within 0.05; a step weight was not." |
| L5 | AnchorPipe beats GraphSAGE in distribution | superiority | Table VIII T1 5101–5120, confirmatory A1 (Holm over 3) | GraphSAGE unscored (strongest **tested**) | stacking (rule candidates + GNN-aware scorer); guard silent | supported for "tested" | "…beats GraphSAGE, the strongest method we tested, by 0.099 F1; the gain comes from stacking GNN probabilities on rule candidates." |
| L6 | It beats the strongest existing method | superiority | as L5 | no fraud-specific GNN | — | partly | Reword as L5, or add CARE-GNN/PC-GNN/BWGNN (I2.5). |
| L7 | The gain replicates | superiority | 4101–4120 +0.088, 4801–4820 +0.088/+0.091, exploratory | GraphSAGE | stacking | supported | "Replicated on two further blocks (exploratory)." |
| L8 | Under transfer-amount overlap it stays level with the rule pipeline, where GraphSAGE and the unguarded pipeline fail | robustness / non-inferiority | T2 5201–5210, A2 and A3 confirmatory | rule pipeline (shipped) | guard (guard-only identical) | supported for amount shift | "Under a transfer-amount shift…" (not "shift" in general) |
| L9 | Under a stronger shift the scored rules lead | limitation | T3 5301–5310, exploratory, −0.032 [−0.085, 0.021] at 90% | scored rules | — | supported | must be stated wherever L8 is |
| L10 | The guard is the contribution | mechanism | ablations T1/T2 (guard only = AnchorPipe) | no guard only | guard | partly / pending I3 | "A flag-rate trigger with rule fallback…"; no claim over standard drift tests |
| L11 | The message-passing gate and evidence anchoring do not help | limitation | H2 −0.063 confirmatory (4101–4120); anchoring +0.009 [0.000, 0.019] | gate off; guard only | — | supported | as stated |
| L12 | Streaming / incremental | efficiency | latency 3701–3705 (shipped pipeline only); hub sweep (AnchorPipe 240 s vs 11 s per stream at 10,000) | 5 s timer | incremental engine (not AnchorPipe) | partly | "The rule pipeline is incremental; AnchorPipe recomputes the GNN on the whole graph each micro-batch (~20× the cost at 10,000 accounts)." |
| L13 | GraphSAGE loses more on an unseen scenario | robustness | 3201–3220, exploratory, drop 0.057 vs 0.001 | GraphSAGE | rule stage needs no labels | supported | as stated, exploratory |
| L14 | The scorer depends on transfer-size features | limitation | 3501–3520 PR AUC 0.77 → 0.55 | — | — | supported | must sit next to L8 |
| L15 | Explanations | limitation | RQ8 deletion test: no better than always naming transfers | — | — | supported (as a limit) | the system bullet must not imply explanations are faithful |
| L16 | Pipeline vs GraphSAGE alone (Table V) | superiority (negative) | 2101–2120 −0.059, raw p 0.025, Holm 0.076 | GraphSAGE | — | not significant after Holm | "GraphSAGE was ahead by 0.059 (Holm p = 0.076)" (I2.1) |

## Inconsistencies the audit exposes (fixed in later items)

| Location | Problem | Item |
|---|---|---|
| Intro | "Two contributions", then four bullets | I4 |
| Intro, line 67 | "Six existing methods" lists five and omits gradient boosting | I4 |
| Results V, line 275; conclusion | "Outperforms every existing method" means every tested method | I2.5 |
| Results, AnchorPipe T4 | "Highest median F1" is a three-way tie at 1.00 | I2.6 |
| Subsection title "…survives shift" | Only a transfer-amount shift was tested | I3 |
| Protocol section | One confirmatory family of four; there are now three (4 + 4 + 3) | I4 |
| Abstract | No cost for the whole-graph GNN; "streaming" applies to the rule pipeline only | I2.3 |
| Abstract and intro | Stacking is not named as the source of the win | I2.4 |

## Searches run for this item

- Meta-blocking ARCS, block purging, weighted edge pruning (survey arXiv 1905.06167, read).
- Failing Loudly (arXiv 1810.11953; NeurIPS 2019).
- BBSE, Lipton et al. (arXiv 1802.03916; ICML 2018).
- Fraud drift and fallback-to-rules (patents and practice articles only).
- GNN OOD detection and fallback (GNNSafe and surveys; no fallback-to-rules found).
- Adamic–Adar.
- Selective prediction under shift.
- GNN stacking with rule candidates for fraud groups (nothing direct; TravelFraudBench, BadLink).
- Stage 0A: 69 papers screened, 23 read (FRAUDAR, Spade, PromoGuardian, CARE-GNN, PC-GNN and others).
