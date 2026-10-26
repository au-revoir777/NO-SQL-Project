# R1 protocol: does a degree cap matter inside the pairwise detector?

Committed before the first run. Amendments are appended below with their reason.

## Question

The paper credits the gain over the rules to "keeping hub links" (C1). Two findings make that untested:
- N1: the rule baseline's recall does not depend on its cap (caps 5–200 all give recall 0.55).
- S1: on hub_heavy the full pipeline is not distinguishable from the scored rules (+0.03 F1, CI −0.11 to 0.17).

R1 isolates the cap inside the full pipeline. Everything else is kept identical: detectors (pairwise shared-attribute, temporal cycle, smurfing), ensemble, tracker, shipped scorer, alert threshold.

## Arms

All arms use the full pipeline (`PROPOSED` overrides), with the hub-aware detector varied as follows:

| Arm | h(d) | Degree cap (`max_attr_degree`) |
|---|---|---|
| `log` | 1/ln(1+d) (shipped) | none |
| `log_cap10` | 1/ln(1+d) | 10 |
| `const` | 1 | none |
| `const_cap10` | 1 | 10 |

Cap semantics: an attribute shared by more than 10 users contributes nothing to any pair, as in rule systems. Cap 10 is the Q4b value. The cap applies to devices, cards and IPs alike.

Reference arm, not tuned again: `static_cap10_scored` (the rules with the shipped scorer, θ_a 0.5 as selected in E1b).

## Tuning (equal budget)

- One hyperparameter per arm: the edge threshold θ_e. The grid is {0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5}, identical for every arm, widened past 1.0 because the constant's earlier selection sat on the old grid edge (R6).
- Alert threshold fixed at the shipped θ_a = 0.8 for every arm, as in E2c.
- Validation seeds 301–303 × the five accuracy scenarios. Select the θ_e with maximum mean ring F1, ties to the lower value.
- If a selection lies on a grid edge, it is reported as such. The grid is not widened again after test results are seen.

## Evaluation

- Fresh test seeds **2001–2010** × the five accuracy scenarios (baseline, high_noise, hub_heavy, adversarial, drift): 50 paired runs per arm. These seeds have not been used before. Later items use other blocks: W2/W3 use 2101–2120 and N-A uses 2201+, each block used once.
- Metrics: ring precision, recall and F1 (Jaccard 0.5, empty run F1 = 0), recall of hub-hiding rings, TTD.
- Locked environment: `requirements-lock.txt`.

## Hypotheses and tests

**Primary (confirmatory family member):** H1, `log` − `log_cap10` in ring F1, two-sided.
- Test: paired, scenario-stratified sign-flip permutation (20,000 flips, seed 0) on the mean difference, with a 95% cluster bootstrap CI (seeds resampled within scenario, 10,000 resamples).
- Holm correction happens at paper level, with the family declared in S1 §2.4.
- Wilcoxon (zsplit) is also reported, for continuity with the paper.

**Secondary (exploratory, uncorrected):**
- `const` − `const_cap10` (cap effect under a constant weight);
- `log` − `const` (discount effect without cap; TOST at δ = 0.05);
- `log_cap10` − `static_cap10_scored` (pairwise detection with the same cap, minus the rules).
- Each is reported per scenario (Δ, 95% t-CI, W/T/L), and hub-hiding recall is reported pooled with a Newcombe CI.

## Falsifiers and wording

- If the H1 CI excludes 0 in favour of `log`, C1 may say: "keeping hub links (no cap) raises ring F1 by X [CI] within the same pipeline; per-scenario effects: …".
- If the CI includes 0 and lies within ±0.05, report: "a degree cap of 10 inside the pairwise detector costs no measurable F1 (equivalent within 0.05)". C1 then cannot claim that keeping hub links matters.
- Otherwise: "not distinguishable; underpowered", with the MDE stated.
- The `log_cap10` − `static_cap10_scored` contrast attributes the remaining gain to pairwise evidence accumulation plus the extra detectors, under the same cap.

## Known limits, stated in advance

- The shipped scorer was trained on candidates of the `log` arm, which may favour it slightly (W3 addresses per-method scorers).
- Hubs in the accuracy scenarios are at most 50 users. A cap of 10 removes them all; a cap of 100 would remove none, so it is not run.

## Amendments

1. (2026-10-26, process) The tuning results and `selected.json` were produced before the test runs, but their commit failed for the same `.gitignore` reason. They are committed together with the test results; the file timestamps show the order. The selection rule was not changed.
