# P8: cleanup (refinement issue P8)

## Done in the paper

- "p ¡ 0.001" in RQ9: the macro `\ThirteenP` holds "< 0.001" and is now set in
  math mode.
- Defined: hysteresis (the two-hit / three-miss tracker rule that the ablation
  turns off); the demo's Oracle view (it overlays ground truth on the dashboard
  and is never shown to the detector). Experiment ids E1/E4 in the text were
  replaced by RQ references or table references.
- The analyst-feedback loop: Fig. 1 contains no analyst loop (its dashed loop
  is the adaptive attacker's). In the training-pipeline figure the loop is now
  marked "product only; not evaluated", and the caption says that no experiment
  in the paper uses it.
- The Table V insight: without the hub-aware detector, precision is 0.98 and
  recall 0.25, so most false candidates come from the hub-aware detector and
  the scorer removes them. Stated in RQ5.
- A real dataset with shared-attribute links: IEEE-CIS (Vesta) is named in the
  Public data threat, with what it can and cannot test. Checked so far: the
  transaction and identity tables, card / address / e-mail-domain fields, masked
  identity and device fields, and the per-transaction `isFraud` label
  (ieee-dataport.org/documents/ieee-cis-fraud-detection and Kaggle write-ups).
  The exact column names should be checked against the Kaggle file headers
  before use (VERIFY). BAF (Jesus et al., NeurIPS 2022 Datasets and Benchmarks)
  was considered and rejected: its rows are single account applications without
  shared identifiers, so no shared-attribute graph can be built.
- The abstract is trimmed (see the final P8 commit).

## Specified, not run: per-detector alert thresholds

- Policy: separate alert thresholds for rings whose detectors include
  `hub_aware` and for rings found only by the transaction detectors (temporal
  cycle, smurfing).
- Selection: a 6 x 6 grid over {0.5, 0.6, 0.7, 0.8, 0.9, 0.95} on validation
  seeds 301-303, 5 accuracy scenarios, maximising mean ring F1.
- Test: seeds 1001-1010 on the E1 streams, paired against the shipped single
  threshold 0.8: Wilcoxon on F1, plus precision and recall.
- Expected table: one row per policy, with P, R, F1, p and d_z.
