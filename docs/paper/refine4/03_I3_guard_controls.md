# I3 — Guard controls

Protocol: `docs/research/round4_protocol.md`, section I3, committed before the runs. All of I3 is exploratory. Results: `results/round4_guard/S0..S6`, `results/round4/trigger_reference.json` and `trigger_traces.csv`. Paper: Table IX (`tab9_guard.tex`) and the guard-control paragraphs in the AnchorPipe section.

## Design

- **Triggers.** Three triggers drive the same fallback inside AnchorPipe:
  - our flag-rate statistic;
  - a KS test on the last 200 transfer amounts (input drift);
  - a KS test on GNN scores (output drift, as in Rabanser et al.).
- **Calibration.** Each trigger fires when the median of its last five batch statistics exceeds the 99.5th percentile on unlabelled hold-out seeds 201–205. The thresholds were τ_amount = 0.340 and τ_score = 0.823.
- **References.** Never fall back, always fall back, the per-stream oracle, the shipped rule pipeline, rules with their own scorer, and GraphSAGE.
- **Shifts.** S0 none; S1 amount overlap; S2 event rate ×3; S3 heavier activity tail; S4 2,000-account hub (`hub_heavy` only); S5 larger rings; S6 ring amounts benign-like. Five scenarios × five seeds each (S4: five streams).

## Results (mean ring F1)

| | S0 | S1 | S2 | S3 | S4 | S5 | S6 |
|---|---|---|---|---|---|---|---|
| Never | 0.855 | 0.371 | 0.871 | 0.785 | 0.949 | 0.832 | 0.732 |
| Flag-rate | 0.855 | 0.609 | 0.871 | 0.785 | 0.949 | 0.832 | 0.732 |
| KS amounts | 0.855 | 0.614 | 0.867 | 0.774 | 0.949 | 0.832 | 0.732 |
| KS scores | 0.855 | 0.598 | 0.871 | 0.785 | 0.949 | 0.832 | 0.732 |
| Always | 0.726 | 0.621 | 0.708 | 0.631 | 0.844 | 0.726 | 0.694 |
| Oracle | 0.863 | 0.624 | 0.876 | 0.793 | 0.967 | 0.844 | 0.801 |
| Rule pipeline | 0.728 | 0.619 | 0.659 | 0.629 | 0.943 | 0.711 | 0.606 |

- **S1 contrasts (90% intervals).**
  - Flag − KS amounts: −0.005 [−0.012, +0.002].
  - Flag − KS scores: +0.011 [+0.002, +0.020].
  - Flag − never: +0.238 [+0.186, +0.290].
- **Firing.** All three triggers fire in 25/25 S1 streams within about 4–5 simulated seconds.

### False and spurious firings (from the traces)

- **Flag-rate trigger.** It fired in two or three early batches of single streams (S3, S5, S6; 1/25 each), with no F1 change.
- **KS on amounts.** It fired in a few late batches (65–88 s) of the `drift` scenario in S0, S2, S3, S5 and S6, whose amounts do drift. There was no F1 change except S2 and S3 (−0.004, −0.011).
- **KS on GNN scores.** It fired in about 36% of batches of every S4 stream (2,000-account hub) from the first batch, with no F1 change. This was corrected in the paper: the first draft said the triggers stayed silent except for single early batches.

## Decision rules applied

1. **Rule 1 applies.** KS on scores is within ±0.03 of the flag rate on S1 and has no S0 false triggers; KS on amounts is also within ±0.03, but it fires late in 2/25 S0 streams. The paper therefore says "the trigger statistic is not the contribution: any of these drift tests serves", in both the abstract and the results.
2. **Rule 2 does not apply.** The flag rate is not better than the input test.
3. **Rule 3.** Under S0 and S2–S6, never is better than always, so firing would cost F1. The triggers did not fire in a way that cost F1, so no shift-specific restriction was needed beyond "the guard helps under a transfer-amount shift".
4. **Rule 4.** The blind spot did not materialise on S6. The GNN pipeline without a fallback stays ahead of the rule pipeline (0.732 vs 0.606). The oracle (0.801) shows room for a better switching rule, and the paper says so.

## Wording change

"Shift-robust" and "survives shift" are gone. The paper now describes AnchorPipe as stacking with a rule fallback, whose level under every shift tested is that of the better of its two scorers, not more.
