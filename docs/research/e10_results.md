# E10 results: ring-level calibration and alert utility

Protocol: [`e10_protocol.md`](e10_protocol.md) (committed before any result;
one amendment, for tied scores at the precision@k cutoff). Data:
`results/e10_ring_alerts/` (clean run at commit `b87dcf8`, `git_dirty: false`
in `manifest.json`; units byte-identical to an earlier run from a dirty tree,
which is kept in `runs/discarded/` and not used). All tables are generated:
[`e10_tables.md`](e10_tables.md) (`python -m fraudsim.experiments.ring_calibration --report docs/research/e10_tables.md`).

These are synthetic-simulator results for the tuned proposed detector on E1's
five scenarios; they say nothing about real-world alert volumes.

## What the numbers show

1. **Ranking is useful.** Pooled over the 50 test runs, 79% of the top 5% of
   alerts are distinct true rings (95% interval 73–86%), 6.1 times the base rate
   of 12.9%. This is lower than it would have been with duplicates counted as
   positives: 42 of the 1,383 eligible units are repeat detections of a ring
   that was already found.
2. **Adversarial evasion halves the ranking quality.** Precision@5% is 0.54
   (0.38–0.72) in the adversarial scenario, against 0.81–1.00 in baseline, high_noise and
   hub_heavy. In drift, precision@10% falls to 0.40, because the scenario produces
   many short-lived false rings (435 false units against 19 true).
3. **The shipped calibration does not transfer to ring-level alerts.** The
   isotonic calibrator inside the scorer was fitted on snapshot rows of the
   training seeds. On ring-level units its ECE is 0.10 (0.09–0.12), barely
   better than the raw model (0.11). A calibrator refitted on ring-level units
   of three separate calibration seeds roughly halves the Brier score (0.085 to
   0.044; Platt and isotonic agree) and brings ECE to 0.03. The miscalibration
   is in the upper range: units in the 0.8–0.9 bin (mean score 0.89) are true
   rings 29% of the time, and in the 0.9–1.0 bin (mean 0.92) 74%
   (`reliability.csv`).
4. **Not everywhere.** In the adversarial scenario no calibrator improves
   (Brier about 0.11 for all four), and in the baseline scenario the refits are
   worse than the raw model, which is already almost perfectly separated there
   (71 units only, so its ECE is not interpreted, per the protocol).
5. **Per ring type** (tracked-ring type, pooled): money cycles and shared-card
   rings are ranked well (precision@10% 0.97 and 0.88); shared-IP and
   mixed-attribute groups are dominated by false units (base rates 5% and 1%),
   which is where hub weighting matters most.

## Alert burden

At the operating threshold (0.8, shipped calibrator) the 50 test runs raise 262
alerts: 165 distinct true rings, 22 duplicates, 75 false. The scenarios are
short (one simulated hour in total across 50 runs), so "alerts per simulated
hour" (262) reflects compressed synthetic time and must not be read as an
operational alert rate.

## Caveats

- 474 tracked rings were scored only while still candidates and never confirmed;
  they cannot alert and are excluded by the protocol.
- ECE intervals come from a percentile bootstrap. ECE is biased upward under
  resampling, so an interval can sit above its point estimate (hub_heavy,
  Platt: 0.024 with interval 0.029–0.064). Brier intervals do not have this
  problem and are the primary comparison.
- The calibration seeds (301–303) are the validation seeds used to tune the
  alert and edge thresholds. They are disjoint from the test seeds, but not
  from the threshold choice.
- Ring-level calibration was refitted here for evaluation only. The detector
  still runs the shipped calibrator; switching it is a separate decision.
