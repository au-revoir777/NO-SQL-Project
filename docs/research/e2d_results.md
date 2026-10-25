# E2d results: per-detector alert thresholds

Protocol: `docs/research/e2d_protocol.md` (3c4db08). Runs: `results/e2d_tuning/`
and `results/e2d_detector_thresholds/`, both recorded on a clean tree.

- **Validation.** On the 36-pair grid (seeds 301-303, 5 scenarios), the best pair
  is (a_hub, a_other) = (0.8, 0.8): the shipped single threshold (mean F1 0.7215).
  (0.8, 0.9) ties, and the tie-break picks the shipped pair. Lowering or raising
  a_hub alone reduces F1: 0.68 at 0.5-0.6, 0.71 at 0.7, 0.68 at 0.9, and 0.30
  at 0.95.
- **Test.** At the selected pair, the policy is the shipped policy. The test run
  reproduces E1's proposed results exactly (P 0.76, R 0.74, F1 0.73 on seeds
  1001-1010), which also confirms that E1 is reproducible.
- **Decision (protocol rule).** No measurable gain. The paper reports separate
  per-detector thresholds as tested and not useful here. The optional policy
  stays in the code, off by default.
