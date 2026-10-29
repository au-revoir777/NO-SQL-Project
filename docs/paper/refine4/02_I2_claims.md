# I2 — Claims fixes

Protocol for the new runs: `docs/research/round4_protocol.md` (committed before the runs). All new seeds are 6001+.

## I2.1 Table V and Holm reporting

- **Before.** Table V reported "GraphSAGE ahead of the pipeline, p = 0.025" without the family correction.
- **After.** Table V's caption now gives Holm p = 0.076 (family 1) and says the difference is not significant after correction. Table VI says its p-values are raw and points to the families in Section III. Table VII says H1 survives Holm over family 2.
- **Families.** The statistics paragraph names the three families (4 + 4 + 3 = 11 tests) and gives raw and Holm p for family 1.

## I2.2 Hub condition: tuned control

- **Decision.** No new run. On validation 301–303 the constant weight gives the same F1 (0.5693) at every θ_e from 0.1 to 0.8. The "can suffice" arm at θ_e = 0.5 is therefore already a tuned control.
- **Paper changes.** The +0.14 contrast is labelled a *declared secondary contrast*, with the flat-threshold note. The preregistered primary (rare attributes barred) is reported as the null result: 0.000, 95% CI −0.028 to +0.028, p 0.98.

## I2.3 "Strongest existing method"

- **Change.** Every "strongest existing" became "strongest method we tested".
- **Ordering.** After I2.5 the ordering is unchanged: GraphSAGE 0.762 is ahead of BWGNN 0.740 on 6001–6020, and BWGNN − GraphSAGE = −0.022 [−0.043, −0.001].

## I2.4 Shift wording

- **Change.** "Survives shift" became "under a transfer-amount shift" everywhere.
- **Stronger shift.** The stronger-shift result is stated next to it, both in the abstract (the pipeline falls to 0.376 without the fallback) and in the AnchorPipe section (scored rules lead by 0.032, exploratory).

## I2.5 Fraud-specific GNN comparator (BWGNN)

- **Model.** BWGNN (Tang et al., ICML 2022), homogeneous version, re-implemented without DGL. The Beta-wavelet thetas match the authors' `calculate_theta2` for order 2. Settings: hidden 64, lr 0.01, 100 epochs, class-weighted BCE, the same graph, features and labels as GraphSAGE.
- **Threshold.** Selected on validation from a 14-value grid (0.1–0.995). Selected 0.95, an interior point; validation F1 0.804.
- **Test results (6001–6020, 100 streams).**

| Method | mean ring F1 |
|---|---|
| AnchorPipe | 0.868 |
| GraphSAGE | 0.762 |
| BWGNN | 0.740 |
| Shipped rule pipeline | 0.706 |

- **Contrasts (exploratory).**
  - AnchorPipe − BWGNN +0.128 [0.099, 0.159]
  - AnchorPipe − GraphSAGE +0.106 [0.082, 0.131] (a fifth replication)
  - BWGNN − GraphSAGE −0.022 [−0.043, −0.001]
- **Decision rule outcome.** "AnchorPipe also beats a fraud-specific spectral GNN (BWGNN)"; GraphSAGE remains the strongest method tested.
- **Not done.** CARE-GNN and PC-GNN were not run. This is stated under Threats ("Comparators").

## I2.6 Every win names its element

- **AnchorPipe.** Its gain is attributed to stacking. With the shipped scorer the same detectors fall below GraphSAGE. With the guard removed (anchoring only), T1 is identical. Anchoring adds +0.009 [0.000, 0.019].
- **Robustness under amount shift.** Attributed to the fallback: guard only = AnchorPipe on T2, and anchoring only falls to 0.358.
- **Hub finding.** Attributed to keeping links of busy attributes: the cap control and cap 27.

## I2.7 Margins and power

- **Margins.** The ±0.05 margin is justified as about one ring in every two to four runs (median of four true rings per run).
- **Key equivalences at ±0.03 (90% intervals).** All three hold:
  - weight shapes −0.018 to +0.002;
  - SagePipe vs EvidPipe −0.017 to +0.023;
  - AnchorPipe vs the rule pipeline under shift −0.018 to +0.001.
- **MDE at 80% power, α 0.05, 100 paired streams.** 0.049 for the N-D primary (so the null rules out effects of about 0.05 and larger, not smaller ones); 0.034 for SagePipe vs EvidPipe.
