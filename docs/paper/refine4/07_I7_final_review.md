# I7 — Final review, exit checklist and claims ledger

## Hostile review (as a programme-committee member would write it)

**Novelty.** The paper has two parts.

- **First part.** It argues that busy shared attributes should be kept as corroborating evidence rather than capped. This is close to the edge weighting and pruning of meta-blocking, to the column weighting in FRAUDAR, and to Adamic–Adar. The preregistered test of the precise design condition (rare attributes barred from linking alone) is null. The condition is supported only by a secondary contrast and a cap-27 run that are exploratory.
- **Second part.** It stacks GNN member probabilities on rule candidates and falls back to a rule scorer when a drift test fires. That is standard stacking plus a selective fallback of the kind discussed in the dataset-shift literature. The authors concede the trigger statistic itself is not new, since a KS test on amounts works as well. I see an engineering pattern, not a method.

**Evidence and soundness.** All evidence is synthetic, from a generator the authors wrote alongside the detector. Ring labels, the evasion strategies and the "amount overlap" shift are all their choices.

- **Gains.** Gains over GraphSAGE replicate across five seed blocks (0.09–0.11 F1). BWGNN is the only fraud-specific comparator. CARE-GNN and PC-GNN are absent, and every GNN sees twelve generic node features, so the "strongest existing method" is weak by construction.
- **Robustness.** The fallback only restores the rule pipeline's level. Under the strongest shift the scored rules lead. Under five other shifts the GNN never failed, so the guard's value rests on one shift family that the authors also designed.
- **Cost.** AnchorPipe recomputes the GNN on the whole graph every micro-batch, about 20 times the incremental pipeline. That undercuts the "streaming" framing of the system.

**Reproducibility and the main reason to reject.** Reproducibility is good. The protocols are committed before the runs, seed blocks are fresh, results carry stream digests, 38 Windows-era rows reproduce on Linux, and an anonymised archive is provided. Retraining the GNNs bit for bit is untested. The single strongest reason to reject is that **no result is shown on real or semi-real data**, so neither the hub finding nor the stacking gain is known to transfer beyond a simulator the authors built.

## How the paper answers each point, and what remains open

| Point | Answer in the paper | Open |
|---|---|---|
| First part is close to meta-blocking / FRAUDAR / Adamic–Adar | Reframed as an empirical *finding*, not a method. Related work cites meta-blocking, block purging, FRAUDAR and Adamic–Adar. The primary null is reported as such, and the 0.14 contrast is labelled secondary | A confirmatory test of the hub condition on fresh seeds |
| Second part is stacking plus fallback | Called exactly that (title, abstract, contribution bullet). Gains are attributed to stacking (shipped-scorer control). The trigger is explicitly not the contribution (Table IX) | — |
| Synthetic only, generator authorship | Threats: Simulator realism, Synthetic labels, Learned components. The conclusion opens "In our simulator". The abstract ends "All data are synthetic" | Evaluation on a public dataset with ring labels (none identified that fits) |
| Weak comparators | BWGNN added; Threats → Comparators names CARE-GNN, PC-GNN and the feature limit. "Strongest" is defined as strongest existing method tested | CARE-GNN / PC-GNN; richer node features |
| Guard rests on one shift | Six other shifts run (Table IX); the outcome is stated: the level is that of the better of the two scorers, not more. The oracle gap (0.801 vs 0.732 on S6) is reported | A better switching rule |
| Cost of the whole-graph GNN | In the abstract ("roughly 20 times") and in Threats → Cost; the System bullet says the GNN is not incremental | An incremental GNN |
| GNN retraining determinism | Stated as untested; saved models are distributed and used | Retrain check |

## Exit checklist

| # | Check | Result |
|---|---|---|
| 1 | No unsupported claim in the abstract or conclusion (ledger) | **Pass.** In the I7 pass the conclusion's "only if" was softened to "helps most when … (exploratory)", "every method we tested" became "every existing method we tested" (SagePipe is within 0.011 of AnchorPipe), and the equivalence margin was aligned to 0.03 |
| 2 | Each retained contribution passes the six-part test or is reworded as an empirical finding | **Pass.** The hub result is labelled *Finding*. AnchorPipe is described as stacking plus fallback, with its element named; I1 judged it incremental, and the paper claims no more |
| 3 | Every win names its element | **Pass** (stacking; fallback; keeping hub links). See 02_I2 §I2.6 |
| 4 | Confirmatory claims show Holm values | **Pass.** Families 1–3 are named; family 1 shows raw and Holm p; Tables V–VII say which is used |
| 5 | Guard controls run, or the claim is limited | **Pass.** Run on 6101–6165, and the claim is limited ("any of these drift tests serves") |
| 6 | Reproducibility items done | **Pass with one stated gap** (bit-for-bit GNN retraining untested; disclosed) |
| 7 | Threats cover synthetic-only evidence, generator authorship, transfer-size dependence, whole-graph GNN cost, no fraud-specific GNN, white-box attacker | **Pass.** Simulator realism / Synthetic labels; Learned components (authorship, transfer size); Cost; Comparators (BWGNN added; CARE-GNN/PC-GNN not); Shift guard and Attacker model (white-box) |
| 8 | All VERIFY marks resolved | **Pass.** 06_I6: all 18 entries exist and the fixes were applied. The Spade claim is qualified ("Spade-equivalent" with a footnote). No VERIFY/PENDING marks remain in the sources (grep) |
| 9 | Banned words ("novel", "first", "outperforms", "state of the art", "foolproof") | **Pass.** Only literal uses remain ("the first 70% of rows", "the first test seeds") |
| 10 | Paper builds | **Pass.** 21 pages, 0 LaTeX errors, 0 undefined references; the abstract has about 150 words |

## Final claims ledger

| ID | Claim (as now worded) | Evidence | Status |
|---|---|---|---|
| L1 | A cap of 10 in the pipeline costs 0.08 ring F1 (Holm p 0.007) | 2001–2010, family 1 | supported, confirmatory |
| L2 | Cap 27 (busy attributes only) still costs 0.051 | 3001–3020 | supported, exploratory |
| L3 | Letting one attribute link a pair costs 0.14; barring rare attributes is null (0.000, p 0.98) | 2401–2420; flat validation F1 for θ_e 0.1–0.8 (I2.2) | supported as a secondary contrast; the primary is null and reported |
| L4 | Two weights that meet the condition are equivalent within 0.03; a step weight costs 0.041 | 2401–2420, 3101– | supported, exploratory |
| L5 | AnchorPipe beats GraphSAGE, the strongest existing method tested, by 0.099 [0.075, 0.123] | 5101–5120, family 3 | supported, confirmatory |
| L6 | AnchorPipe beats BWGNN by 0.128 [0.099, 0.159]; GraphSAGE stays ahead of BWGNN | 6001–6020 | supported, exploratory |
| L7 | The stacking gain replicates (0.09–0.11 on five blocks) | 4001, 4101, 4801, 5101, 6001 | supported |
| L8 | Under a transfer-amount shift the fallback holds the rule pipeline's level (non-inferior); GraphSAGE and the unguarded pipeline fail | 5201–5210, family 3; 6111–6115 | supported for amount shift only |
| L9 | Under the stronger shift the scored rules lead by 0.032 | 5301–5310 | supported, stated next to L8 |
| L10 | The trigger statistic is not the contribution; a standard KS test serves | 6101–6165 (Table IX) | supported, exploratory |
| L11 | Under five other shifts the GNN did not fail; AnchorPipe's level is that of the better scorer, not more; the oracle shows room | 6121–6165 | supported, exploratory |
| L12 | The rule pipeline is incremental; AnchorPipe's GNN costs about 20 times as much | hub sweep; shared-run timings | supported (wall-clock indicative) |
| L13 | GraphSAGE loses more when a scenario is left out | 3201–3220 | supported, exploratory |
| L14 | The scorers depend on transfer-size features | 3501–3520 | supported; stated in Threats and the conclusion |
| L15 | Explanations are no more faithful than always naming a transfer feature | RQ8 deletion test | supported (as a limit) |
| L16 | Without a GNN, GraphSAGE is ahead of the rule pipeline (Holm p 0.076, not significant) | 2101–2120, family 1 | reported as not significant |
| L17 | The message-passing gate hurts (−0.063); anchoring adds at most 0.019 | 4101–4120 family 2; 5101–5120 | supported, reported as rejected designs |
| L18 | 38 Windows-era rows reproduce on Linux | `check_reproduction.py` | supported |
