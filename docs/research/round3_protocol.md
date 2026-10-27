# Round 3 protocol (R1, R3, R4, R5, R6 experiments)

Committed before any of these runs. Locked environment (`requirements-lock.txt`, `requirements-w2.txt`). All seed blocks below are fresh: none appears in `results/` or in earlier protocols, and none overlaps the GNN-extension blocks (311–320, 4001–4720, 7001–7005, 8001–8005). Every block is used once.

All tests here are **exploratory**. The paper's confirmatory family of four is closed. Report scenario-weighted paired differences with 95% cluster bootstrap CIs and stratified sign-flip p-values; equivalence only if the 90% CI lies within ±0.05 F1.

## R1: cap sweep inside the full pipeline (seeds 3001–3020 × 5 scenarios)
- **Arms.** The shipped pipeline (1/ln(1+d), θ_e 0.3, θ_a 0.8, shipped scorer), with the attribute-degree cap set to none, 10, 27, 50 or 250.
- **Reference arm.** Rules (cap 10, cycle rule) with their own scorer (W2 selection).
- **Metrics.** F1, hub-hiding recall, false rings per run, per-scenario F1.
- **Why cap 27.** At θ_e = 0.3 an attribute with more than about 27 users cannot link a pair alone, so cap 27 removes exactly the attributes the discount makes "busy".
- **Diagnostic.** For the rules arm on `hub_heavy`, the rule (Q1–Q4) whose candidate matched each detected hub-hiding ring.

## R3: constant weight with an explicit degree cutoff (seeds 3101–3120 × 5)
- **Arms.**
  - shipped 1/ln(1+d), θ_e 0.3;
  - `step_27`: h(d) = 1 if d ≤ 27, else 0.2, at θ_e 0.3. Rare attributes link alone; busy ones need a second piece of evidence, as with 1/ln at 0.3.
  - constant, θ_e 1.0 (Table V's constant row: one attribute decays below 1.0, so every link needs two pieces).
- **Question.** Is the adaptive-ring gap (24/28 vs 11/28) about rare attributes linking alone? Is the discount's shape irrelevant once that property is matched?

## R4: GraphSAGE generalisation, decoy strength, operating points
- **Scorers** (no test seeds used). The pipeline scorer is retrained with the shipped protocol on the proposed pipeline's own candidates (seeds 101–110, six scenarios), for parity across arms:
  - `pipe_all`: all scenarios;
  - `pipe_loso_X`: without scenario X;
  - `pipe_noamount`: amount features zeroed (R5).
- **GraphSAGE LOSO** (training only): five models, each trained without one accuracy scenario (seeds 101–110; `scale_sweep` kept; the W2 settings: 40 epochs, seed 0).
- **LOSO test (seeds 3201–3220, each scenario X).** Compare `gnn_all` with `gnn_loso_X` (node threshold 0.95, as W2 selected), and `pipe_all` with `pipe_loso_X`.
  - **Metric:** the F1 drop (all minus LOSO) per method, and the difference of drops (GraphSAGE minus pipeline), paired by stream.
  - **Outcome wordings:** if GraphSAGE's drop exceeds the pipeline's (CI excludes 0): "GraphSAGE's advantage depends on having seen the scenario in training". If not: "both generalise similarly to an unseen scenario of this generator".
- **Decoy sweep (seeds 3301–3310, `high_noise`, decoys per action 0/1/2/4/8).** Arms: proposed, GraphSAGE unscored, GraphSAGE + scorer, hybrid, all trained at default strength. Metric: decoy-ring recall and F1 per strength (ranges over 10 seeds).
- **Operating-point sweep (seeds 3401–3405 × 5).**
  - Proposed, hybrid and GraphSAGE + scorer at θ_a ∈ {0.3, 0.5, 0.7, 0.8, 0.9}; GraphSAGE unscored at node thresholds {0.8, 0.9, 0.95, 0.97, 0.99}.
  - Report precision at matched recall and alerts per run at matched recall. This is a sweep on test streams, so it is descriptive only.
- **PR AUC CI.** A cluster-bootstrap CI for the existing W3 ring PR AUC difference (no new runs).

## R5: amount features (seeds 3501–3520 × 5; generator variant 3601–3610 × 5)
- **Ablation.** `pipe_all` vs `pipe_noamount` (amount_mean_log, amount_cv and near_threshold_frac zeroed in training and inference; the coefficients are checked to be 0).
- **Generator variant.** Benign transfer median raised from 120 to 2,000, so benign and ring amounts overlap (scenario override `simulation.amount_median = 2000`). Arms: `pipe_all`, `pipe_noamount`, GraphSAGE unscored, rules with their own scorer. All are trained on the default generator.
- **Outcome wordings:**
  - the scorer's gain survives (`pipe_noamount` within 0.05 F1 of `pipe_all`, and similar under overlap): "the scorer does not depend on transfer-size features";
  - it shrinks: report the size of the drop in the abstract's precision sentence.

## R6: latency in one environment (seeds 3701–3705)
- **Runs.** Growing-hub `scale_sweep` at 1,000, 5,000, 10,000 and 20,000 users; incremental vs 5 s timer.
- **Setup.** Revision container, run alone after every other job has finished.
- **Reporting.** Min–max and median over the five seeds; no p-values.
