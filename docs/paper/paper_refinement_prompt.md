# Paper Refinement Prompt: Hub-Aware Incremental Fraud Ring Detection

Paste this whole file into a new chat and attach the PDF (plus LaTeX source, result CSVs, and simulator configs if available).

---

## ROLE

You are a critical reviewer and co-author helping me revise an IEEE-style conference paper before submission. Be direct and specific. I want targeted fixes, not a rewrite. Treat my results as real data I have already produced, and treat any claim the data does not support as something to reword or to back with a new experiment.

## PAPER

**"Hub-Aware Incremental Fraud Ring Detection on Streaming Transaction Graphs"** (attached).

Summary: synthetic-simulator evaluation of a hub-aware edge weight `h(d) = 1/ln(1+d)` with exponential time decay, micro-batch incremental detection over a k-hop dirty region with fan-out caps (250 first hop, 20 later hops), a calibrated logistic-regression ring scorer (19 features, isotonic calibration), and per-alert explanations (contributions, evidence subgraph, counterfactuals). Baselines: static Cypher rules (cap 10 / cap 100), Louvain, connected components. Deployed stack: Neo4j + Redis Streams.

## WORKING RULES

1. **One issue at a time**, in the priority order below (P1 to P8). After each, stop and wait for my feedback before continuing.
2. **Minimal edits.** Present each change as: `location -> old text -> new text -> one-line reason`. Do not rewrite sections I did not flag.
3. **Never invent** numbers, citations, results, or dataset properties. If a fix needs a new experiment, give the exact spec (scenario, seeds, methods compared, metric, expected table or figure layout) and mark the affected text `[PENDING RESULT]`.
4. **Verify before asserting.** Flag any claim you cannot confirm from the paper itself. Mark every reference you suggest as `VERIFY` until I confirm it exists and says what you claim.
5. **Check consistency** after every change: abstract, intro contributions (C1 to C4), tables, figure captions, conclusion, threats to validity. List everything else the change touches.
6. **Keep my voice.** Plain, precise, hedged where the evidence is thin. No marketing language.
7. If you disagree with one of my priorities below, say so briefly and explain, then proceed as I asked unless I reply.

## ISSUES, IN PRIORITY ORDER

### P1. Attribution of the headline result
F1 0.73 vs 0.21 compares a system **with** the calibrated scorer against Cypher rules **without** it. The ablation shows the scorer is the largest single contributor (F1 0.72 -> 0.39 without it, precision 0.28). The mechanism-level comparison in Fig. 4 (best F1 0.58 vs 0.55) is much closer and has no confidence intervals.

Tasks:
- (a) Spec "static cap 10 + scorer", "static cap 100 + scorer", and "Louvain + scorer" rows for Table II (same seeds, same scorer protocol).
- (b) Spec confidence intervals for Fig. 4 (bootstrap or per-seed).
- (c) Rewrite the abstract, the RQ1 paragraph, and the Table II caption so the gain is attributed correctly to the weight, the scorer, and the incremental engine separately.

### P2. C1 lacks statistical support
Removing hub weighting costs -0.12 F1 with p = 0.161 and dz = 0.42 (20 paired runs, underpowered). Replacing it with a constant helps `high_noise` (0.54 -> 0.68). Hub-hiding recall is 35/52 vs 33/52 against cap 10, and the cap's recall on those rings comes largely from the cycle rule (30/90 with Q3 off).

Tasks:
- Spec a higher-powered `hub_heavy` ablation (30+ seeds, paired), reporting recall, precision, F1, dz, and p.
- Spec a comparison of weight functions: `1/ln(1+d)`, `1/d`, `1/sqrt(d)`, a soft cap, and constant.
- Reword C1, the abstract, and the conclusion to what the current evidence supports, with a version to use if the new experiment confirms the effect.

### P3. The 250-user fan-out limit is a hidden degree cap
The first hop only crosses attributes with up to 250 users, so a ring behind a larger hub is invisible to the incremental engine. This is the same failure C1 claims to remove. Fig. 6 tests hubs only up to 200, and "incremental = full recomputation" holds only because every hub is below 250.

Tasks:
- Spec a test with hub sizes 500, 2,000, and 10,000 (incremental vs full vs cap baselines; recall, F1, region size, latency).
- Spec an alternative that avoids the hidden cap (for example, expand through a hub only when the touched user is already in a candidate pair).
- Draft an explicit limitation paragraph for Section III-C and for Threats to Validity.

### P4. Latency claim framing
The 623x speed-up is against full recomputation on every 50-event batch, which no one would deploy. Other problems:
- 3 seeds only; the incremental CI (36.1 ± 44.2 ms) is wider than its mean.
- Full-recompute numbers at 50k and 100k users are confounded by memory pressure on the 7.7 GB machine.
- The region shrinks only because the scenario scales attributes with users while hub sizes stay fixed.
- TTD is unchanged versus the timer baseline (9.3 s vs 9.5 s).

Tasks:
- Reframe 623x as a worst-case bound, not a headline.
- Spec a timer-based full-recompute baseline at several intervals (1 s, 5 s, 30 s) with cost per unit time and TTD.
- Spec a scale scenario where hub sizes grow with the population.
- Rewrite the abstract and conclusion wording accordingly.

### P5. Positioning, novelty, and citations
Tasks:
- Check whether Fraudar (log-degree down-weighting for camouflage resistance) and Spade (incremental dense-subgraph fraud detection) should be cited and contrasted. Mark both `VERIFY`. Do not state their details from memory as fact.
- State plainly that the contribution is applying a degree discount to shared-attribute ring detection in a streaming setting, not the formula itself (Adamic-Adar style).
- Replace secondary or mismatched citations with primary sources, each marked `VERIFY`:
  - Louvain [18] is a differential-privacy paper; use the original Louvain paper (Blondel et al.).
  - [19] stands in for Adamic-Adar; use the original.
  - [17] stands in for densest subgraph; use Goldberg or Charikar.
  - [25] and [26] used for Platt and isotonic calibration; use the originals (Platt, Zadrozny and Elkan, or Niculescu-Mizil and Caruana). [26] is image-classification temperature scaling.
  - Text says "Azbergenov" but [25] lists "Azbergen"; fix.
- Provide a revised Related Work paragraph that includes the new positioning.

### P6. Evaluation validity
Tasks:
- **Generalisation:** spec a leave-one-scenario-out test for the scorer (train on five scenario types, test on the sixth), since train and test share a generator.
- **White-box adaptive attacker:** spec attacker strategies that exploit the detector's parameters: ring size outside 3 to 25, edge density below 0.75, transfer weight kept under `beta_max`, many distinct hubs per ring. Compare to the current 4-strategy attacker (18/22 detected vs 9/11).
- **Calibration:** re-run the main results with the ring-level calibrator (ECE 0.10; refit Brier 0.085 -> 0.044), or justify in the text why not.
- **Scorer metrics:** report ring-level metrics before the snapshot-level AUC 0.982, which is inflated by many correlated snapshots per ring.
- **Statistics:** add multiple-comparison correction (Holm or Benjamini-Hochberg) to the p-values, and state clearly that Table II pools scenarios.
- **"Live stream" framing:** F1 falls from 0.61 to 0.43 at 100 events/s, and the Neo4j stack saturates at 35 to 52 events/s. Reword claims to match, and suggest cheap engineering fixes to test (batched Cypher reads with `UNWIND`, cached hub degrees).

### P7. Explainability claims
The conclusion says explanations are "stable and their evidence is faithful", but:
- 69% of alerts have no single-feature counterfactual.
- Only 29% reproduce the same first counterfactual after retraining.
- Stability of linear-model contributions is close to guaranteed.
- Evidence precision 1.00 is near-tautological because the evidence subgraph is built from the matched ring.
- "103 counterfactuals" vs "262 alerts, 69% have none" is hard to reconcile as written.

Tasks:
- Define the unit of analysis for each number and fix the reconciliation.
- Soften the conclusion to match Section VI-C.
- Spec one non-tautological faithfulness test (for example, deletion or insertion tests on evidence edges).

### P8. Cleanup
- Fix the typo "p ¡ 0.001" -> "p < 0.001" in RQ9.
- Define or remove: hysteresis (Table V), Oracle view (Fig. 3), E1 and E4 (use RQ numbers).
- Evaluate or remove the analyst-feedback loop shown in Figs. 1 and 2.
- Trim the abstract (about 230 words) to the 4 or 5 claims the evidence fully supports.
- Add the Table V insight: without the hub-aware detector, precision is 0.98 and recall 0.25, so most false positives originate in the hub-aware detector and the scorer cleans them up. Propose per-detector alert thresholds as a cheap improvement and spec the test.
- Suggest one real dataset with shared-attribute links (for example IEEE-CIS Fraud or Bank Account Fraud, both `VERIFY`) as added or future work, stating what labels it has and what it can and cannot test.

## OUTPUT FORMAT PER ISSUE

1. **Diagnosis:** two or three sentences on why this is a problem for a reviewer.
2. **Experiment spec(s):** scenario, seeds, methods, metrics, expected table or figure. Use a table where it helps.
3. **Text changes:** `location -> old -> new -> reason`, with `[PENDING RESULT]` placeholders where numbers are not yet available.
4. **Ripple effects:** other places in the paper that must change.
5. **Open questions for me:** at most two.

Then stop and wait.

## START

Begin with **P1 only**. Give me, in order:
1. The experiment spec for the new baseline rows and the Fig. 4 confidence intervals.
2. The exact replacement text for the abstract, the RQ1 paragraph, and the Table II caption, with `[PENDING RESULT]` placeholders.
3. Any inconsistencies elsewhere in the paper that this change creates.

Then wait for my feedback.
