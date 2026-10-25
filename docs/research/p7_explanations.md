# P7: explanation claims (refinement issue P7)

No new experiment. The text was changed to match what E12 measured.

## Units of analysis (all from `docs/research/e12_tables.md`)

| Number | Unit |
|---|---|
| 262 | alerts: ring units whose peak calibrated score is at least 0.8 (test seeds 1001-1010, 5 scenarios) |
| 81 | alerts with at least one single-feature model counterfactual |
| 103 | model counterfactuals over those 81 alerts (an alert can have several) |
| 0 / 103 and 103 / 103 | counterfactuals that flip the decision, as shipped and after the fix |
| 69% | alerts with no counterfactual (181 of 262) |
| 0.026 | median contribution drift per alert at 5% noise |
| 29% | alerts whose first counterfactual is the same under the retrained scorer (77 of 262) |
| 1.00 / 1.00 | median evidence precision / coverage over correct (tp) alerts |

## What changed

- RQ8 states the unit, and reconciles 103 counterfactuals with 81 of 262 alerts.
- Stability is described as close to guaranteed for a linear model.
- Evidence fidelity is described as showing the right accounts, not as
  explaining the score.
- The conclusion no longer says "stable and faithful".

## Specified, not run: deletion test of the evidence

- Units: the 165 correct (tp) alerts of E12.
- For each alert, rebuild the view at its peak time and compute three things:
  1. the score with all evidence links removed (shared-attribute links among
     members, and internal transfers);
  2. the score with each evidence type removed on its own;
  3. a control: the score with the same number of the members' links removed
     that the evidence does not list (random draw, 20 repeats).
- Metric: score drop under evidence deletion minus the score drop under the
  control, paired per alert (Wilcoxon). Also the rank agreement between the
  per-type drops and the displayed contributions of the features each type
  feeds.
- Expected table: one row per ring type, with median drops (evidence vs
  control) and the paired p.
