# Prompt 2: R4 / N-A, N2, N3, N4 (novelty track)

Sources:
- R1 (`04_r1.md`, seeds 2001–2010);
- N-D (`docs/research/followups_protocol.md`, seeds 2401–2420, `diag/nd_contrasts.txt`);
- W3 (`05_w2_w6.md`, seeds 2101–2120);
- the region traces (`02_w1.md` §0).

## R4 / N-A. Exactness of the bounded region

### N-A "check first": the transfer term

In code (`graph/store.py::expand`) transfers in the window are crossed at every hop with no fan-out limit. So a pair with transfers between them is always in the same region when either member is touched.

**The transfer term is not a hole.** The paper's argument fails elsewhere:
- for k ≥ 2 over-limit attributes;
- for pairs whose weight falls without either member being touched (decay, hub growth);
- for ring extraction (components plus greedy peeling), which is not local.

### Pair-level condition (lemma, proof from the code)

Setup:
- Let u be touched in a batch, L = 250 the first-hop limit, and θ_e the edge threshold.
- Let W(u,v) = Σ_a h(d_a)·δ_a + T(u,v) ≥ θ_e, with a non-zero attribute term.

In fan-out mode, v is in u's region unless:
- every attribute u and v share has degree > L, and
- they have no transfer in the window.

In that case W(u,v) ≤ k·h(L+1), where k is the number of shared over-limit attributes.

**Sufficient condition for no missed pair:** k_max · h(L+1) < θ_e, where k_max is the largest number of over-limit attributes a pair shares.

| Weight, θ_e | h(L+1), L = 250 | Pairs that can be missed |
|---|---|---|
| 1/ln(1+d), 0.3 | 0.181 | k ≥ 2 |
| 1/ln(1+d), 0.2 | 0.181 | k ≥ 2 |
| 1/d (θ_e 0.1) | 0.004 | k ≥ 26 |
| constant, 1.0 | 1·δ < 1 | k ≥ 2 (a single attribute decays below 1.0) |
| constant, 0.5 | 1·δ | k ≥ 1 |

**The paper's claim needs correcting.** §III-C says the constant fails because one busy attribute reaches the threshold. That holds only for θ_e ≤ δ. At the selected θ_e = 1.0 the constant has the same k ≥ 2 condition as 1/ln.

**The "bound" rule closes the pair-level gap exactly.** It crosses an over-limit attribute toward v when the sum of h over shared over-limit attributes reaches θ_e. In E5b it never added a user (15/15 runs), so no pair in those streams had k ≥ 2.

### Ring-level exactness fails, for both weights

At the 500-account hub, incremental and full recomputation differ ring by ring in 2/5 runs (1/ln) and 3/5 runs (constant). The cause, from the traces:
- **Partial regions:** a ring none of whose members is touched enters a region only partly.
- **Non-local peeling:** greedy peeling of a 389–539-user connected component returns the ring on the full graph but not on the region's sub-component, even with every member present.

A runtime certificate would have to cover the extraction step: require the region to contain the touched users' whole thresholded component. In these streams that component is most of the graph, so certifying it removes the saving.

### Verdict

N-A as a contribution does not pass. The sufficient condition is a one-line bound (the "trivial" dismissal applies), and it does not give ring-level exactness, which is what the paper claims. Instead:
- §III-C states the pair-level condition and the bound rule as a design note, with the corrected constant-weight explanation.
- Threats states that ring-level equality with full recomputation is observed for hubs ≤ 50 and not guaranteed above.

R4's count of pairs linked only by k ≥ 2 over-limit attributes is 0 in the 500 / 2,000 / 10,000 runs (inferred from bound = fan-out in 15/15 runs).

**Text (§III-C), old:**
> "The first-hop limit is itself a degree cap on the region: a pair whose only link is an attribute shared by more than 250 users never enters the same region. For the hub-aware weight this costs nothing, since one such attribute contributes at most 1/ln 252 ≈ 0.18, below the edge threshold, so a full pass would not link the pair either; a weight that lets one busy attribute reach the threshold, such as a constant, does lose such pairs (Section V)."

**Text (§III-C), new:**
> "The first-hop limit is itself a degree cap on the region. Transfers are always crossed, so a pair can be missed only if all the attributes it shares have more than 250 users and it has no transfer in the window; its weight is then at most k·h(251) for k such attributes. With h(d) = 1/ln(1+d) and θ_e = 0.3 this requires k ≥ 2, and a variant that crosses an over-limit attribute whenever the shared over-limit weight could reach θ_e never added a user in our runs. Equality with full recomputation is a property of pairs, not of rings: candidate rings are extracted by greedy peeling of connected components, which is not local, so at hubs of 500 and more accounts individual rings differed between the two modes in both directions (Section V)."

Reason: corrects the refuted mechanism and states the condition exactly.

## N2. Candidate contributions

Each candidate is checked against the six-part test: claim, mechanism-level object, isolation control, falsifier, prior art, dismissal rebuttal.

### N-A: exactness certificate

**Not retained** (above). Cost spent: analysis only. Risk realised: the bound is trivial, and ring-level exactness fails.

### N-B: sequential calibration of ring alerts

- **Claim:** treat "alert at first crossing, score = max over snapshots" as a stopping rule and control the false-alert rate directly.
- **Object:** a ring-level, time-aware calibrator.
- **Control:** the ring-level isotonic refit (Brier 0.085 → 0.044).
- **Falsifier:** realised false-alert rate above target on held-out seeds.
- **Prior art:** conformal and e-value false-discovery-rate control is an active area, including for graph anomaly detection (VERIFY). It needs far more ring-level units than the 1,383 available.

**Not run.** Stays in Threats (Calibration) and future work.

### N-C: evidence persistence across rotation and slow activity

- **Claim:** keep decayed evidence of unlinked identities beyond the window to catch rotating and slow rings.
- **Control:** window-matched (several half-lives).
- **Effort:** highest. It needs new generator behaviour and long scenarios.

**Not run.** Stays in Threats (rotation 7/25 and slow 4/27 found on seeds 2101–2120; W3).

### N-D (added from the paper's data): a busy attribute must not suffice alone

**Claim sentence:** "We show that keeping hub links improves ring detection only when a busy attribute cannot link a pair by itself, so that it counts as one piece of evidence beside a second attribute or internal transfers. A degree cap removes that evidence, and a weight that lets one attribute suffice links every co-member of a hub. Given the condition, the shape of the discount does not matter."

- **Object:** a design condition on the pair rule, h(d)·δ < θ_e for busy attributes, tested in two forms: a degree discount (1/ln(1+d) at θ_e 0.3), or a per-attribute cap at 0.29 or a constant at θ_e 1.0 (the two-evidence rule).
- **Isolation controls, all on fresh seeds:**

| Contrast (seeds) | Δ F1 [95% CI] | Hub-hiding recall | Reading |
|---|---|---|---|
| Keep links vs cap 10, 1/ln (R1, 2001–2010) | **+0.084 [0.048, 0.121]**, p 0.002 | 29/52 vs 9/52 | removing hub evidence hurts |
| Keep links vs cap 10, constant (R1) | +0.057 [0.039, 0.077] | 31/52 vs 7/52 | same |
| Constant two-evidence vs one-evidence (N-D, 2401–2420) | **+0.137 [0.106, 0.168]**, p < 0.001; hub_heavy +0.44 | 72/104 vs 9/104 | letting a hub suffice alone hurts |
| 1/ln vs constant, both "hub cannot suffice" (R1) | −0.028 [−0.068, 0.009] | 29 vs 31/52 | shape does not matter |
| 1/ln + two-evidence vs constant two-evidence (N-D) | −0.008 [−0.020, 0.003] | 68 vs 72/104 | shape does not matter |
| **Primary N-D: 1/ln two-evidence vs shipped 1/ln** | **0.000 [−0.028, 0.028]**, p 0.98 | 68 vs 67/104 | no overall gain from also barring *rare* attributes from linking alone; trade-off: drift +0.15 (false rings 1.8 → 0.05), adversarial −0.15 (adaptive 22/32 → 10/32) |

- **Falsifier (preregistered):** "two-evidence not better than one-evidence for either weight". Not met: the constant contrast is +0.137. The primary contrast is null, so the two-evidence rule is **not an improvement** over the shipped weight, only an equivalent alternative overall, with a scenario trade-off.
- **Prior art:**
  - Entity-resolution meta-blocking weights candidate pairs by the inverse size of the blocks they share (ARCS), and Block Purging drops oversized blocks: the same discount-versus-cap choice (Papadakis et al., VERIFY).
  - FRAUDAR's column weighting (verified) and Adamic–Adar discount by degree.
  - I found no fraud-ring study that isolates "hub as one of two pieces of evidence" against a cap and against a one-evidence weight on held-out data.
- **Dismissal:** "This is just a threshold on Adamic–Adar." Rebuttal: the controls show that the *threshold relation* (whether a busy attribute can link alone), not the discount, determines the result. Two different weights satisfying it are indistinguishable (−0.008), and the same weight violating it loses 0.44 F1 on hub_heavy.
- **Cost:** done (R1 and N-D: 900 test runs).
- **Risk:** reviewers may call it a design guideline rather than a contribution. It replaces C1's current "hub-aware weighting" claim.

## N3. Ranking and choice

| Rank | Candidate | Status | Decision |
|---|---|---|---|
| 1 | N-D, "a busy attribute must not suffice alone" (with R1) | tested, supported as a mechanism (isolation controls on two fresh seed blocks) | **retain** as the C1 contribution |
| 2 | N-A, pair-level region condition | analysed; ring-level exactness fails | demote to a §III-C design note and Threats |
| 3 | N-B, sequential calibration | not run | Threats and future work |
| 4 | N-C, evidence persistence | not run | Threats and future work |

This differs from the prior ordering (N-A core). The data moved it: N-A's ring-level claim fails at large hubs, while R1 and N-D give clean isolation results.

Weaknesses that stay open, for Threats:
- the GNN outperforms on F1 (W3);
- drift and noise weakness (W3);
- rotation and slow rings;
- ring-level calibration;
- synthetic-only evidence;
- single-laptop timing;
- no white-box attacker.

## N4. Preregistration summary and rewrite

### Retained contribution: C1′

| Item | Content |
|---|---|
| Seeds | R1 2001–2010; N-D 2401–2420; both fresh, declared before running |
| Hypotheses | R1-H1: no cap > cap (1/ln); N-D-H1: two-evidence 1/ln > shipped 1/ln; secondary: const two > const one |
| Metrics | ring F1 (primary), hub-hiding recall, false rings per run |
| Controls | cap 10 (removes hub evidence); one-evidence constant (hub suffices alone); weight shape under the condition |
| Falsifiers | R1-H1 CI including 0; both two-vs-one contrasts null |
| Outcome | R1-H1 supported (+0.084, p 0.002); N-D-H1 null (0.000); const two vs one supported (+0.137) |

### Six-part checklist (C1′)

| Test | Pass? |
|---|---|
| 1. Claim sentence | pass |
| 2. Mechanism-level object (a condition on h, θ_e and degree; not a module combination) | pass, with risk ("guideline") |
| 3. Isolation control on preregistered seeds | pass (R1, N-D) |
| 4. Falsifier stated | pass |
| 5. Prior-art check | **partial**: meta-blocking (VERIFY), FRAUDAR, Adamic–Adar named; searches not exhaustive |
| 6. Dismissal rebuttal | pass (−0.008 vs −0.44) |

### C2–C4 checklist

| | 1 | 2 | 3 | 4 | 5 | 6 | Retain as contribution? |
|---|---|---|---|---|---|---|---|
| C2 incremental engine | pass | **fail** (standard dirty-region recomputation; Spade does exact incremental peeling) | partial | pass | pass | fail | **No.** Keep as a system component with measured cost |
| C3 calibrated, explained scorer | pass | **fail** (LR + isotonic) | pass (ablation) | pass | pass | fail | **No.** Keep as component; the isotonic counterfactual defect is a reported finding |
| C4 simulator and evaluation | pass | fail (artifact) | n/a | n/a | partial | fail | **No** as a scientific contribution; keep as an artifact |

C2–C4 must not be listed as contributions in the novelty sense. The introduction can list them as "system and evaluation", separate from the contribution.

### Rewrite (outcome: C1′ supported; GNN outperforms on F1; W3b pending)

- **Title options:**
  - (a) "Keeping Hub Links: Pairwise Evidence for Fraud Ring Detection on Streaming Transaction Graphs";
  - (b) keep "Hub-Aware Incremental Fraud Ring Detection on Streaming Transaction Graphs", defining hub-aware as "keeps hub links, but never lets a hub link a pair alone".

  I recommend (a). The data does not support "hub-aware weighting" as the source of gains.

- **Abstract (draft):**
  > Fraud rings share devices, cards and network addresses and move money among themselves. Rule-based detectors suppress busy shared attributes, such as office gateways and carrier NAT, with a degree cap. We study a streaming pipeline that instead keeps those links as pairwise evidence, detects incrementally on the region each micro-batch touches, and scores candidate rings with a calibrated model. On a deterministic simulator with ring-level ground truth and five evasion strategies, isolation experiments on fresh test seeds show what matters. Within the same pipeline, a degree cap costs 0.08 ring F1 (95% CI 0.05–0.12) and most hub-hiding rings. A weight that lets a busy attribute link a pair on its own costs 0.14. Given that a hub can never suffice alone, the shape of the degree discount makes no difference. Against tuned rules, Louvain, Leiden and FRAUDAR-style peeling, each with its own scorer and at least the same tuning budget, the pipeline improves ring F1 by 0.06–0.26. A GraphSAGE classifier trained on ring labels from the same generator reaches higher F1 (0.78 vs 0.72), mainly on drifting and noisy scenarios, while the pipeline ranks rings better and finds more adaptive and decoy rings `[W3b sentence]`. Slow and identity-rotating rings are rarely found by any method, and all results are synthetic.

- **C1–C4 (draft):**
  - **C1** (contribution): the evidence condition, with R1 and N-D numbers.
  - **System:** incremental engine (pair-level condition; cost measured), calibrated explained scorer.
  - **Evaluation:** simulator, preregistered protocols on fresh seeds, per-method scorers, five existing baselines including GraphSAGE.

- **Conclusion (draft):** the first sentence states C1′. The second gives the comparison to existing methods, including the GNN result. The third covers the limits.

Refuted-outcome versions are not needed for C1′, since its tests have run. The W3b sentence has one version per outcome in `05_w2_w6.md` (W5) and is filled after W3b.

## Ledger updates

| ID | New status |
|---|---|
| C1 (new C1′) | **supported** (R1, N-D) |
| C1 "hub-aware weighting is the contribution" | **unsupported**: remove |
| C2 "exact incremental detection" | **partly**: pair-level condition; ring-level equality only for hubs ≤ 50 |
| A1 "caps hide rings" | **supported for a cap inside the pairwise pipeline** (9/52 vs 29/52); not for the rules |
| A4 "exact discount matters little" | **supported**, given the condition (−0.008 [−0.020, 0.003]) |
