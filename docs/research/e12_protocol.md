# E12: explanation quality (protocol)

Workstream A2 of the Phase 2 plan (`docs/phase2/phase2_prompt.md`, P11, where
it is called "E10 explanations"; E10 and E11 were already taken by the
ring-alert and early-warning experiments, so it is E12 here). This protocol is
committed **before** any E12 result is computed. Changes after the first run
are listed under "Amendments" with their reason.

It answers the specification's RQ4, "are the explanations any good?", with
measurements of what the product shows an analyst: the feature contributions,
the model counterfactuals, and the evidence subgraph.

## Units and data

- **Streams:** E10's test streams, re-run exactly as E10 does
  (`alert_units.run_scored`, tuned proposed method, shipped scorer
  `models/ring_scorer_lr.joblib`, SHA-256 in the manifest). That means E1's five
  scenarios (`baseline`, `high_noise`, `hub_heavy`, `adversarial`, `drift`) and
  test seeds 1001–1010. Each run's stream digest is recorded, and must equal
  E10's for the same (scenario, seed).
- **Unit:** E10's unit, a tracked ring at its peak confirmed scoring event
  (same unit, score and tp/duplicate/fp label definitions). E12 also stores the
  member set at that event.
- **Explained population:** units whose peak calibrated score is at least the
  alert threshold 0.8 ("alerts"). These are the rings whose explanations an
  analyst reads. Counts of all units and of alerts are reported per scenario.
- **Actionable features:** `ACTIONABLE` in `scoring/explanations.py`, the
  features the product proposes counterfactual changes for. All other features
  are **non-actionable**.

## Metrics (fixed before results)

1. **Counterfactual validity.** For each alert, the model counterfactuals are
   the ones the product would show. That is
   `explanations.counterfactuals` restricted to model counterfactuals:
   actionable features with positive contribution, at most two, using
   `RingScorer.counterfactual_value`, kept only if the target is non-negative
   and below the current value (or above it, for `hub_exposure`).

   For each, set that one feature to its target value, re-score with the
   deployed scorer (calibrated), and record:
   - **valid:** the new score is below 0.8;
   - **in range:** the target lies within the range of that feature over all
     E12 units (a plausibility check, not a guarantee);
   - **relative change:** |target − current| divided by the feature's standard
     deviation over all E12 units.

   Reported per feature and overall: count, validity rate, in-range rate, and
   the median and IQR of the relative change. The hub-aware **rule**
   counterfactual is not re-run through the detector (it is a statement about
   the rule's threshold, not the scorer) and is excluded. That is a stated
   limitation.
2. **Stability under non-actionable noise** (after Artelt et al. 2021). For
   each alert and each noise level δ ∈ {0.01, 0.05}, draw K = 20 perturbations.
   Each multiplies every non-actionable feature by (1 + u), with u ~ U(−δ, δ),
   seeded by (scenario, seed, ring_id, δ). For each perturbation x′:
   - **contribution drift:** ‖c(x′) − c(x)‖₁ / ‖c(x)‖₁, where c is the vector
     of the 19 contributions;
   - **top-3 agreement:** Jaccard of the top-3 features by |contribution|;
   - **counterfactual agreement:** whether the first proposed counterfactual
     names the same feature;
   - **target drift:** for that feature, |target(x′) − target(x)| divided by
     the feature's standard deviation.

   Per alert, average over the K draws; report the median and IQR over alerts.
   With δ = 0, every drift is 0 and every agreement is 1 (unit-tested).
3. **Consistency after retraining** (after Movin et al. 2025). Train a second
   scorer with the shipped training code (`scoring.train`): same model type
   (logistic regression), scenarios, fit fraction and labelling, on **training
   seeds 111–120**, disjoint from the shipped scorer's 101–110, its test seeds
   201–205, the validation seeds 301–303 and the test seeds 1001–1010. For each
   alert (alerts as defined by the shipped scorer):
   - **rank correlation:** Spearman of the two contribution vectors;
   - **top-3 agreement** (Jaccard);
   - **counterfactual agreement:** same first counterfactual feature;
   - **decision agreement:** the second scorer also scores the unit ≥ 0.8.

   Report the median and IQR of the correlations and the agreement rates. This
   measures the explanation's dependence on the training sample, not a defect
   per se.
4. **Evidence fidelity** (Oracle, simulator ground truth). For each unit, M is
   its members at the peak event:
   - **tp/duplicate units:** precision |M ∩ T| / |M| and coverage |M ∩ T| / |T|,
     where T is the matched true ring's all-time members (as in E10's
     labelling);
   - **all units:** the share of M who belong to any true ring.

   Reported as median and IQR by label and by scenario, for all units and for
   alerts. Labelled "Oracle (simulator ground truth)".
5. **Counterfactual feature importance** (after De Meulemeester et al. 2026).
   The product's model counterfactuals change one feature at a time, so a
   counterfactual's importance is fully that feature's. For each actionable
   feature, report how often it is the first counterfactual, its validity rate,
   and the median score drop it causes (current calibrated score minus the
   counterfactual's). This is the single-feature case of their measure, stated
   as such.
6. **Semi-global view:** the mean |contribution| of each feature over alerts,
   by ring type (tracker ring type), and the share of alerts where it is in the
   top 3.

## Reporting

- Distributions, not selected examples: medians, IQRs and counts per scenario
  and overall. No example ring is quoted as typical.
- All tables are generated by `python -m fraudsim.experiments.explanation_quality
  --report docs/research/e12_tables.md` from `results/e12_explanations/*.csv`.
  Results and limitations go in `docs/research/e12_results.md`, written only
  after the CSVs exist.
- Provenance: the manifest records the git commit and dirty state, the model
  SHA-256 for both scorers, seeds, the stream digests and library versions.
  A run from a dirty tree is moved to `runs/discarded/` and repeated.

## Amendments

None yet.
