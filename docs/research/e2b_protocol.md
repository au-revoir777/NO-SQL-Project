# E2b and E2c: statistical support for the hub weight (C1)

Committed before any E2b/E2c result exists. Motivation: refinement issue P2
(`docs/paper/paper_refinement_prompt.md`). In E2, removing hub weighting cost
0.12 F1 with p = 0.161 (20 paired runs), and replacing it with a constant even
helped `high_noise`; E3b (P1) found the weight's best F1 on shared-attribute rings
indistinguishable from the cap's. C1 needs a powered test and a comparison of
weight functions.

## Weight functions h(d), d = number of users sharing the attribute (d >= 2)

| Name | h(d) | Note |
|---|---|---|
| `inverse_log_degree` | 1 / ln(1 + d) | shipped (C1) |
| `inverse_degree_plain` | 1 / d | new |
| `inverse_sqrt_degree` | 1 / sqrt(d) | new |
| `soft_cap` | 1 / (1 + exp((d - 10) / 2)) | new; logistic step at the Review II cap of 10 |
| `none` | 1 | constant (the E2 "w/o hub weighting" ablation) |

The rest of the detector (time decay, transaction term, peeling, size and
density limits) and the pipeline (all five detectors, ensemble, tracker, shipped
scorer, alert threshold 0.8 from `configs/tuned.json`) are unchanged.

## Edge threshold per weight function (validation seeds only)

The weights live on different scales, so each function gets its own edge
threshold: grid {0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0}, scenarios baseline,
high_noise, hub_heavy, adversarial, drift, seeds 301-303, alert threshold 0.8;
the value with the highest mean ring F1 is kept (ties: the lower value). If the
best value of a function sits on an edge of the grid, that is reported, not
silently extended.

## E2b: powered hub_heavy test

- Scenario `hub_heavy` (rings hidden behind benign hubs), seeds 1001-1030 (30 paired runs).
- All five weight functions at their selected edge thresholds.
- Primary test: `inverse_log_degree` vs `none` on run F1, paired Wilcoxon
  (zsplit, as in the paper), Cohen's d_z, median difference. Also precision,
  recall and recall of hub-hiding rings.
- Secondary: `inverse_log_degree` vs each other function, Holm-corrected over
  the four comparisons.

## E2c: weight functions across scenarios

- Scenarios baseline, high_noise, hub_heavy, adversarial, drift; seeds 1001-1010
  (the E1 streams; 50 paired runs per function).
- Same five functions and thresholds; `inverse_log_degree` vs each other, Holm
  over four comparisons; F1 per scenario.

## Decision rule (stated in advance)

C1 is worded as an F1 improvement over a constant weight only if E2b's primary
test has Holm-free p < 0.05 with the shipped function ahead. Otherwise C1 is
worded as a recall/reach property (rings behind hubs become reachable) and the
paper says the F1 gain over a constant weight is not established. The choice of
1/ln(1+d) over the other functions is claimed only if E2c shows it ahead after
Holm correction; otherwise the paper says the functions perform similarly.

## Outputs

`results/e2b_tuning/`, `results/e2b_hub_heavy/`, `results/e2c_weight_functions/`,
`results/e2b_hub_heavy/selected_edge_thresholds.json`,
`docs/research/e2b_tables.md` (generated), `docs/research/e2b_results.md`.

Amendments, if any, are appended below with their reason.
