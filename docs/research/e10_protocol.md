# E10: ring-level calibration and alert utility (protocol)

Workstream C of `master_prompt2.md` (Phase 2 plan, P10a). This protocol is
committed **before** any E10 result is computed. Changes after the first run
must be listed under "Amendments" with their reason.

## Why a new experiment

The E1–E7 result files store one aggregate row per run, with no per-alert
scores or labels, so ring-level calibration cannot be computed from them.
E10 re-runs the E1 configuration of the proposed method on the same scenarios
and seeds, and logs every scored tracked ring. E1's files are not touched
(they are frozen by `docs/audit/m0_baseline.json`).

## Configuration

- Method: the tuned proposed detector exactly as in E1 (`tuned_proposed()`:
  static Cypher and community off, hub-aware edge threshold 0.3; alert
  threshold 0.8 from `configs/tuned.json`), shipped scorer
  `models/ring_scorer_lr.joblib` (SHA-256 recorded in the manifest).
- Scenarios: E1's five (`baseline`, `high_noise`, `hub_heavy`, `adversarial`,
  `drift`).
- Seeds: **calibration** 301–303 (the validation seeds already used to tune
  the thresholds; never test seeds) and **test** 1001–1010 (E1's test seeds).
  The scorer itself was trained on seeds 101–110, so the three groups are
  disjoint.

## Unit, score and label (fixed before results)

- **Unit:** one tracked ring (stable `ring_id`) within one run.
- **Eligible:** units that were scored at least once while `confirmed`. Alerts
  are only raised on confirmed rings, so candidate-only units cannot become
  alerts. The number of non-eligible units is reported.
- **Score:** the unit's **peak** calibrated risk over its scoring events while
  confirmed. This is the quantity the alert rule compares with the threshold
  ("alert once risk ≥ threshold"). Ties go to the earliest event. The raw model
  probability and the 19 features of that peak event are stored, so other
  calibrators can be applied offline to the same event.
- **Label**, using the members **at the peak event** (not the ring's final
  members, so nothing after the scored moment is used):
  - `tp`: Jaccard ≥ 0.5 with the full member set of some true ring that
    became active during the run (the matching rule of `evaluate_run`), and
    it is the highest-scoring unit matched to that true ring (ties: earliest
    peak, then ring id);
  - `duplicate`: matches a true ring that already has a `tp` unit;
  - `fp`: matches no true ring.
  A ring detected repeatedly therefore counts once. Duplicates are **not**
  positives in any metric: they count as negatives in precision@k (they cost
  review time) and are reported separately.
- **Truth** comes from the simulator ledger and is used only offline, after
  the run. It never feeds the detector or scorer.

## Metrics (per scenario and pooled over scenarios; test seeds only)

- Counts: eligible units, `tp`, `duplicate`, `fp`, true rings, simulated hours.
- Base rate p = tp / eligible units.
- Precision@k% and lift@k% for k = 1, 5, 10: rank units by score (descending;
  ties by run, then ring id), take the top ⌈k% · n⌉, precision = share of `tp`,
  lift = precision / p. **Undefined** (reported as empty, never 0) when n = 0 or
  p = 0.
- Alert burden at the operating threshold 0.8: alerts (units with score ≥
  threshold), how many of them are tp, duplicate and fp, and alerts per
  simulated hour.
- Calibration of the score against the binary label (tp = 1, else 0): Brier
  score; ECE with 10 equal-width bins (weighted mean |accuracy − confidence|)
  and, as a check, 10 equal-mass bins; reliability table (bin, n, mean score,
  positive rate).
- Per ring type (the tracked ring's `ring_type`) where a type has ≥ 20
  eligible units; smaller groups are reported as counts only.

## Calibrator comparison

All candidates map the same raw model probability (at the peak event) to [0, 1]:

1. `shipped`: the isotonic regression stored in the model (fitted at training
   time on snapshot rows of seeds 101–110);
2. `uncalibrated`: the raw model probability;
3. `platt_ring`: logistic regression on logit(raw), fitted on **calibration-seed
   units only**;
4. `isotonic_ring`: isotonic regression, fitted on calibration-seed units only.

Compared on test-seed units only. The alert-burden numbers use the shipped
calibrator, which is the one the detector actually runs.

Note: the peak is chosen with the shipped score. Under another monotone
calibrator the peak event is the same, because the order of events is
preserved; non-monotone mappings are not used.

## Uncertainty

95% intervals from a **cluster bootstrap over seeds** (2,000 resamples; seeds
resampled with replacement within each scenario, all units of a drawn seed
kept), because units of one run are not independent. Reported with the number
of seeds. Comparisons between calibrators are paired (the same resampled seeds
for every calibrator). ECE is not interpreted where fewer than 100 eligible
units are available.

## Outputs

`results/e10_ring_alerts/`:
- `units.csv`: one row per eligible unit;
- `runs.csv`: one row per run (counts, non-eligible units, simulated hours,
  stream digest);
- `manifest.json`: provenance;
- `summary.csv`, `reliability.csv`, `calibrators.csv`: from
  `fraudsim.experiments.ring_calibration`.

## Amendments

None yet.
