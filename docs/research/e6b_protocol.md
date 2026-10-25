# E6b: scorer generalisation across scenarios and ring-level scorer metrics

Committed before any E6b result exists. Motivation: refinement issue P6
(`docs/paper/paper_refinement_prompt.md`). The scorer's training and test seeds
are disjoint but come from the same generator and the same scenarios. Its
reported AUC (0.982) is computed over ring *snapshots*, many of them correlated
snapshots of the same ring.

## Data

The rows of the shipped scorer's training run `dd98f740ea8c`
(`runs/training/dd98f740ea8c/{train,test}_rows.csv`, written by
`fraudsim.scoring.train`; the training rows are seeds 101-110, the test rows
seeds 201-205, six scenarios). They are copied unchanged to
`results/e6b_generalisation/rows/`, with their SHA-256 recorded. No new
simulation is run.

**Sanity check first.** Refitting on all training rows with the shipped
procedure (StandardScaler + logistic regression, then isotonic calibration on
the last 30% of each run) must reproduce the shipped test metrics to 3
decimals. If it does not, the analysis stops and the difference is reported.

## Analysis 1: leave one scenario out

For each of the six scenarios S:
- fit on the training rows of the other five scenarios (same fit/calibration
  split), evaluate on S's test rows;
- reference: the model fitted on all six scenarios, evaluated on the same
  rows of S.

Report per S: ROC AUC, PR AUC, ECE and Brier for both models, at the snapshot
level and at the ring level (below), plus the drop from reference to
held-out.

## Analysis 2: ring-level metrics

A ring unit is (scenario, seed, ring_id) in the test rows. Its score is the
maximum calibrated score over its snapshots, and its label is the maximum
snapshot label (it matched a planted ring at some point). Report ROC AUC,
PR AUC and the number of units for the shipped scorer, next to the snapshot-level
numbers, and the same in the leave-one-out folds.

## Outputs

`results/e6b_generalisation/` (rows, `results.csv`, manifest),
`docs/research/e6b_tables.md` (generated), `docs/research/e6b_results.md`.

Amendments, if any, are appended below with their reason.
