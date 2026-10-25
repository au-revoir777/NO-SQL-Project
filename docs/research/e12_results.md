# E12 results: explanation quality

Protocol: [`e12_protocol.md`](e12_protocol.md) (committed before any result,
with amendment 1 made before the first run). All numbers below come from
`results/e12_explanations/` and are reproduced in the generated
[`e12_tables.md`](e12_tables.md). Cells are medians with the interquartile range
unless they are rates.

## Data

The 50 test streams of E10 (five scenarios × seeds 1001–1010) were re-run with
the shipped scorer. Every stream digest equals E10's. That gives 1,383 units,
the same count as E10's test split, of which 262 are alerts (peak calibrated
score ≥ 0.8). Collection ran from commit `eef051e` with a clean tree. The
retrained scorer for metric 3 was trained with the shipped training code on
seeds 111–120 (model and training record in the same directory).

## Findings

1. **Every counterfactual the product showed before E12 was wrong.** As
   shipped, none of the 103 model counterfactuals proposed for alerts moved the
   calibrated score below the threshold (0 of 103; first counterfactual 0 of 81
   alerts). The cause is amendment 1: the target aimed just below an isotonic
   breakpoint, but the calibrator interpolates, so the score stayed above 0.8.
   With the corrected computation (the product now), all 103 do (103 of 103).
   101 of 103 corrected targets lie within the observed range of their feature.
   The 2 that do not both concern `density`.
2. **Most alerts get no model counterfactual.** 181 of 262 alerts (69%) have
   none. Their score is carried by features the product does not treat as
   actionable. In the semi-global view, the typical transfer size
   (`amount_mean_log`) has the largest mean |contribution| for every ring type
   and is in the top 3 for 87–100% of alerts. Its variation (`amount_cv`) and,
   for money cycles, `cycle_length` and `cycle_present` follow. Where a
   counterfactual exists, it is mostly `hub_adjusted_weight` (68 of 81 first
   choices). The median required change is 1.2 [0.6, 2.0] standard deviations
   of the feature, and the median score drop is 0.121 [0.115, 0.136].
3. **Explanations are stable under small noise in the non-actionable
   features.** With ±1% noise, contribution drift is 0.005 [0.004, 0.006], and
   the top-3 features and the first counterfactual feature agree in every draw
   for the median alert (and the whole IQR). With ±5% the drift is 0.026
   [0.022, 0.031], with the same agreement. The counterfactual target moves by
   0.03 and 0.15 feature standard deviations at the median.
4. **Retraining keeps the ranking of evidence but changes which change is
   proposed.** Against a scorer trained on disjoint seeds, the Spearman
   correlation of the contribution vectors is 0.916 [0.902, 0.930], and the
   median alert keeps its top-3 features (IQR 0.5–1.0). But the first proposed
   counterfactual is the same feature for only 77 of 262 alerts (29%), and
   87% of the alerts (229 of 262) are also alerts under the retrained scorer.
   Agreement on the counterfactual is lowest in `baseline` (1 of 39) and
   highest in `hub_heavy` (30 of 57). An analyst should read a counterfactual
   as a property of this model, not of the ring.
5. **The evidence subgraph is the right group when the alert is right**
   (Oracle, simulator ground truth). For true-positive alerts, the median
   evidence precision and coverage are both 1.000 (coverage IQR 0.833–1.000).
   Duplicates look the same. For false-positive alerts, the median share of
   evidence members who belong to any true ring is 0.000 (IQR 0.000–0.096).
   Wrong alerts are mostly made of benign accounts, not partial views of real
   rings.

## Limitations

- The hub-aware rule's counterfactual (a statement about the rule's edge
  threshold) was not re-run through the detector and is not measured.
- Counterfactuals change one feature at a time, with the others fixed. Some
  feature pairs move together in reality (for example `density` and
  `hub_adjusted_weight`), so a valid single-feature change can still be an
  implausible ring. The in-range check is only a plausibility screen.
- The stability noise touches only non-actionable features, as the protocol
  states. Noise in actionable features would change the counterfactual by
  construction.
- One shipped model, one retrained model, five scenarios, simulated data. The
  consistency numbers describe this pair of training samples, not a
  distribution over retrainings.
