# E2d: separate alert thresholds for hub-aware and transaction-only rings

Committed before any E2d result exists. Motivation: refinement issue P8. The
ablation without the hub-aware detector has precision 0.98 at recall 0.25, so
most false candidates come from the hub-aware detector. One alert threshold for
all rings may therefore be too low for hub-aware rings or too high for the rest.

## Policy

Rings whose detector sources include the hub-aware detector use threshold
`a_hub`; all other rings use `a_other`. The shipped policy is
`a_hub = a_other = 0.8`.

## Selection (validation seeds only)

- Grid: `a_hub`, `a_other` in {0.5, 0.6, 0.7, 0.8, 0.9, 0.95} (36 pairs).
- Scenarios: baseline, high_noise, hub_heavy, adversarial, drift.
- Seeds: 301-303.
- Rule: highest mean ring F1; ties go to the pair closest to (0.8, 0.8).

## Test

- Seeds 1001-1010 on the E1 streams.
- Selected pair vs the shipped single threshold (`proposed` in
  `results/e1_baselines`).
- Statistics: paired Wilcoxon (zsplit) on F1, d_z, precision and recall.

## Decision rule

The paper recommends per-detector thresholds only if the test difference is
significant at p < 0.05. Otherwise it reports the result as no measurable gain.

## Outputs

`results/e2d_tuning/`, `results/e2d_detector_thresholds/`,
`docs/research/e2d_results.md`.

Amendments, if any, are appended below with their reason.
