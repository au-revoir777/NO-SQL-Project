# E1b: baselines with the calibrated scorer, and intervals for the frontier

Committed before any E1b result exists. Motivation: refinement issue P1
(`docs/paper/paper_refinement_prompt.md`). Table II compares the full pipeline,
which includes the calibrated scorer, with rule and community baselines that are
not scored, so the headline F1 gap mixes the candidate generator (hub-aware
weight, incremental detection) with the scorer. E1b adds scored baselines;
E3b adds confidence intervals to the existing frontier experiment (E3).

## E1b: scored baselines

| Item | Value |
|---|---|
| Scenarios | baseline, high_noise, hub_heavy, adversarial, drift (as E1) |
| Test seeds | 1001-1010 (the identical streams of E1; paired by scenario and seed) |
| Validation seeds | 301-303 (threshold selection only) |
| Scorer | the shipped `models/ring_scorer_lr.json` / `.joblib`, unchanged (decided by the author) |
| Confirmation | two-hit tracker, as every E1 method |

Methods, each the E1 baseline of the same name with `scored=True`:

| Name | Candidates | Scorer |
|---|---|---|
| `static_cap10_scored` | static Cypher Q1-Q4 (incl. 3-cycle rule), degree cap 10 | shipped |
| `static_cap100_scored` | as above, cap 100 | shipped |
| `louvain_scored` | E1 Louvain communities | shipped |

Connected components get no scored row: in E1 they never produce a group within
the ring size limits (F1 0.00), so the scorer has nothing to score.

**Alert threshold.** For each method separately, the grid
{0.2, 0.3, 0.5, 0.7, 0.8, 0.9} (the grid used for the proposed method) is run on
the validation seeds and the threshold with the highest mean ring F1 is kept
(ties: the lower threshold). Each method is then run on the test seeds at its
selected threshold, and also at the a-priori 0.5, mirroring the
"Proposed, a-priori thresholds" row.

**Comparison.** Every row is compared with the tuned proposed method of E1
(`results/e1_baselines/results.csv`, method `proposed`) on the same
(scenario, seed) streams: paired Wilcoxon signed-rank on run F1 (a run with no
flags counts F1 = 0), median difference and Cohen's d_z. Holm correction over the
family of all Table II rows compared with the proposed method: the four unscored
baselines, the proposed method with a-priori thresholds, and the three scored
baselines at their selected thresholds (8 tests). Rows at the a-priori 0.5 are
reported in a secondary table with uncorrected p-values.

**Reading.** Within the scored group, differences isolate the candidate
generator. The difference between a baseline's unscored and scored rows is the
scorer's contribution to that generator. Known caveat, to be stated in the paper:
the scorer was trained on candidates of the proposed pipeline, so it sees some
distribution shift on rule and Louvain candidates; E13 covers a model trained on
Louvain groups.

## E3b: intervals for the frontier (analysis only, no new runs)

Data: `results/e3_frontier/results.csv` (4 scenarios x seeds 1001-1005 = 20 runs
per sweep point).

- 2,000 bootstrap resamples (numpy seed 0), resampling seeds with replacement
  within each scenario (stratified), recomputing the micro-averaged precision
  and recall of every sweep point, as plotted.
- 95% percentile intervals for the precision and recall of each point; drawn as
  error bars on the frontier figure.
- Headline: best F1 of hub-aware + scorer minus best F1 of cap 10 + scorer,
  each best re-selected inside every resample (so the selection is not
  optimistic); reported as point estimate and 95% percentile interval.
- Also: paired Wilcoxon on per-run F1, each family at its full-sample best alert
  threshold.

## Outputs

- `results/e1b_tuning/`, `results/e1b_scored_baselines/` (rows, manifests)
- `results/e1b_scored_baselines/selected_thresholds.json`
- `results/e3b_frontier_ci/frontier_ci.json`
- `docs/research/e1b_tables.md` (generated), `docs/research/e1b_results.md`

Amendments, if any, are appended below with their reason.
