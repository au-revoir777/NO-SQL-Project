# AnchorPipe: results (docs/research/anchor_protocol.md)

The protocol was committed in b216878, before any code. Selections were committed before any test block (`results/anchor/selected.json`, 9e31159).

## Confirmatory (Holm over three; all supported)

| ID | Block | Contrast | Estimate | Interval | Outcome |
|---|---|---|---|---|---|
| A1 | T1 5101–5120 (100 streams), in distribution | AnchorPipe − GraphSAGE | +0.099 | 95% CI [0.075, 0.123]; p < 0.001 | Supported |
| A2 | T2 5201–5210 (50), amount overlap 2,000 | AnchorPipe − SagePipe | +0.239 | 95% CI [0.212, 0.267]; p < 0.001 | Supported |
| A3 | T2 | AnchorPipe − shipped pipeline (better of pipeline/rules by block mean) | −0.008 | 90% CI [−0.018, 0.001], above −0.05 | Supported (non-inferior) |

## All blocks (F1; false rings per run)

| Method | T1 | T2 amounts 2,000 | T3 amounts 5,000 | T4 hub 500 (median) | T4 hub 2,000 (median) |
|---|---|---|---|---|---|
| **AnchorPipe** | **0.868** (1.0) | 0.616 (3.5) | 0.572 (5.1) | **1.00** | **1.00** |
| Guard only (no anchoring) | 0.860 | 0.615 | 0.572 | 1.00 | 1.00 |
| Anchor only (no guard) | 0.868 | 0.358 (24.8) | 0.317 (32.0) | 1.00 | 1.00 |
| SagePipe | 0.857 | 0.376 (22.4) | 0.330 (29.5) | 1.00 | 1.00 |
| GraphSAGE | 0.770 | 0.000 | 0.008 | 0.86 | 0.86 |
| Hybrid | 0.749 | 0.556 | 0.495 | 0.86 | 0.91 |
| Shipped pipeline | 0.698 | **0.624** | 0.579 | 0.77 | 0.86 |
| Rules + own scorer | 0.647 | 0.571 | **0.604** | 0.86 | 0.86 |

**Guard fallbacks (ring scorings routed to the shipped scorer).** Validation: 0. T1: 0. T4: 0. Development amount 1,000: 2,963. T2: 6,628. T3: 7,955.

**Exploratory contrasts.**
- **T1:** AnchorPipe vs hybrid +0.119, vs shipped pipeline +0.170, vs rules +0.221, vs SagePipe +0.011 [−0.005, 0.029], vs guard-only +0.009 [0.000, 0.019].
- **T2:** vs rules +0.045 [−0.006, 0.096], vs hybrid +0.060.
- **T3:** vs SagePipe +0.242; vs shipped pipeline −0.007 [−0.013, −0.002]; vs rules −0.032 (90% CI [−0.085, 0.021]), not shown equivalent.

## Reading

- **The shift guard is the working component.** Under amount shift, GraphSAGE's flag-rate statistic jumps from a median of 0.045 (reference) to near 1. The guard fires in every shifted stream and never in distribution.
- **Evidence anchoring adds nothing measurable.** It gives +0.009 in distribution (CI touches 0) and nothing under shift. It is reported as a tested and rejected design, like the message-passing gate.
- **Under the strongest amount shift the scored rules lead slightly.** The fallback scorer itself uses transfer-size features (R5).
