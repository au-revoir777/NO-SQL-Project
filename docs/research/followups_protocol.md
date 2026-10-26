# Follow-up experiments (prompt 2: N-D, R2, R5, R6): protocol

Committed before any of these runs. Locked environment.

## N-D: two-evidence rule (novelty candidate, from N2)

**Hypothesis.** What separates rings from the hubs they share is not the degree discount. It is that a pair needs **two independent pieces of evidence**:
- each shared attribute counts at most as one piece, however rarely it is shared;
- the transfer term counts as another piece.

Evidence so far:
- R1: a constant weight at θ_e 1.0 does at least as well as 1/ln(1+d).
- W3: on drift, the shipped weight at θ_e 0.3 produces 1.9 false rings per run, because one rarely shared attribute (h(2) ≈ 0.91) links a pair alone. The constant at 1.0 produces 0.3.

**Arms.** Full pipeline, shipped scorer, θ_a 0.8, nothing tuned. The θ values follow from the rule.

| Arm | h(d) | θ_e | Single attribute can link a pair? |
|---|---|---|---|
| `log_one` (shipped) | 1/ln(1+d) | 0.3 | yes, if d ≤ about 27 |
| `log_two` | min(1/ln(1+d), 0.29) | 0.3 | no |
| `const_one` | 1 | 0.5 | yes (until decayed) |
| `const_two` | 1 | 1.0 | no (decay < 1) |

**Seeds.** Fresh **2401–2420** × five accuracy scenarios = 100 paired runs.

**Primary (paper family member 4).** `log_two` − `log_one`, ring F1, two-sided. Test: stratified sign-flip permutation with a cluster bootstrap 95% CI.

**Secondary.**
- `const_two` − `const_one`;
- false rings per run;
- per-scenario Δ;
- hub-hiding recall.

**Falsifier.** If `log_two` is not better than `log_one`, and `const_two` not better than `const_one`, the two-evidence explanation is refuted and is not a contribution.

## R2: scored rules alongside unscored comparisons

The rules with their own scorer, in the W2 validation selection (cap 10, cycle rule on, θ_a 0.7), added as an arm on the **same streams** as:
- Table III (5 scenarios × seeds 1001–1010);
- Fig. 6 (hub sizes 5–200, seeds 1001–1005);
- the large-hub runs (500 / 2,000 / 10,000, seeds 1001–1005);
- Fig. 8 (event rate and ring size, seeds 1001–1005).

Purpose: replace scored-vs-unscored comparisons. These are additions to existing paired figures, so they reuse those figures' seeds and are reported as exploratory.

## R5: 10,000 users

The E4b-2 growing-hub `scale_sweep` at 10,000 users, seeds **2501–2505**, incremental vs 5 s timer. Report cost per simulated second as min–max over seeds; no p-value. 50,000 users is not run: the timer arm needs about 25 min per run on the test laptop class, so the text will say "at 20,000 users".

## R6: widened grids

On validation seeds 301–303, extend the edge-threshold grid for 1/d to {0.02, 0.05} and for the soft cap to {1.2, 1.5, 2.0}.
- If the selection moves, those two weights are re-run on the E2c and E2b test seeds (1001–1010, 1001–1030), paired with the recorded shipped arm, and the RQ5 text is updated.
- If it does not move, the text states that the optima are interior or at the end of a meaningful range.
