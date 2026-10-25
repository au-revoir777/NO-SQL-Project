# E13 and E14 results: a learned baseline and evasion strength

Protocol: [`e13_e14_protocol.md`](e13_e14_protocol.md), committed before any
result, with amendment 1 (candidate groups), made after the first training run
failed and before any usable result. All numbers come from
`results/e13_learned_baselines/`, `results/e13_tuning/` and
`results/e14_evasion_strength/` (commit `26a99f1`, clean tree; the failed first
training run is kept in the manifest). They are tabulated in the generated
[`e13_tables.md`](e13_tables.md) and [`e14_tables.md`](e14_tables.md).

## E13: gradient boosting on rule-free candidate groups

`tabular_gb` scores Louvain communities (density filter off) with a calibrated
gradient-boosting model on the same 19 ring features. It was trained like the
shipped scorer. Its alert threshold was chosen on validation seeds 301–303:
0.7, with mean validation F1 0.440, against the proposed method's 0.722 on the
same seeds. All 100 test streams have E1's digests, and the proposed method's
re-run reproduces E1 exactly (mean F1 0.731).

1. **The rule stage earns its place overall.** Pooled over the five scenarios
   and seeds 1001–1010, ring-level F1 is 0.731 for the proposed method and
   0.555 for `tabular_gb`. The median paired difference is −0.257 (Wilcoxon
   p < 0.001, rank-biserial −0.85). Recall drives it: 0.735 against 0.378.
   Node-level AUC is 0.851 against 0.689.
2. **The difference is largest where hubs and evasion matter.** In
   `hub_heavy`, F1 is 0.793 against 0.400 (p = 0.002), and in `adversarial`
   0.591 against 0.244 (p = 0.004). In `baseline`, `high_noise` and `drift`,
   the differences (−0.07 to −0.10 at the median) are not significant at 10
   pairs (p = 0.06–0.13).
3. **Where the learned baseline is better** (reported as the protocol requires):
   - its **precision** is higher in every scenario except `baseline` (tied at
     1.000), at 0.936 pooled against 0.764;
   - it raises fewer alerts (96 per simulated hour against 276);
   - its **user-level F1** is higher in `high_noise` (0.554 against 0.540)
     and `drift` (0.544 against 0.509).

   It is the more conservative detector: almost every ring it flags is real,
   but it misses most rings that hide behind hubs or evade.

## E14: camouflage strength (high_noise, every random ring using the swept mode)

How much each cell can say depends on how many swept-mode rings it contains
(counted over the 10 seeds):
- **decoy edges:** 21–24 rings per value;
- **identity rotation:** 11 rings per value. Only 27 of the 50 streams differ
  across its five values, so in 60-second streams rotation rarely triggers;
- **low-and-slow:** 11, 11, 9, 5 and 0 rings at ×1, ×2, ×4, ×8 and ×16. Rings
  slowed further do not become active within the run, so the ×16 cell has no
  rings to recall.

Decoy edges are therefore informative. The other two modes are underpowered:
the CIs are wide, and few paired differences are non-zero.

4. **Decoy edges break the community-based methods, not the proposed one.**
   - The proposed method's swept-mode recall stays at 0.74–0.82 from 0 to 8
     decoys per action.
   - Louvain falls from 0.36 to 0.00, and `tabular_gb` (which uses Louvain
     groups) from 0.48 to 0.05.
   - With one or more decoys, both are significantly below the proposed method
     (median difference −0.58 to −0.83, p = 0.002–0.004).
   - Static Cypher with a degree cap of 10 keeps recall (0.68–0.73) but at a
     precision of 0.03–0.05.
5. **Low-and-slow: the proposed method finds few of these rings.** Its recall
   is 0.17–0.25 where rings exist.
   - Static Cypher (cap 10) recovers more of them (0.42–0.75), at a precision
     of about 0.04.
   - `tabular_gb`'s **overall F1 exceeds the proposed method's** at ×2 (0.63
     against 0.58) and ×4 (0.67 against 0.61), with precision 1.00.
   - None of these differences is significant (p ≥ 0.5 on swept recall), but
     they are reported here and in the README as the protocol requires.
6. **Identity rotation:** the proposed method's recall is 0.42–0.62. Louvain
   and `tabular_gb` stay at 0.00–0.17, and the differences reach p = 0.06 at
   best with 11 rings.

## Limitations

- One learned baseline. GraphSAGE (optional in the plan) was not run: not
  done, not a negative result.
- `tabular_gb`'s candidates depend on Louvain. Its weakness under decoys is
  partly the grouping's, not the classifier's. A learned model over the
  proposed method's own candidates would be a different comparison (an
  ablation of the scorer).
- E14's streams are the 60-second `high_noise` scenario. Strong low-and-slow
  and rotation settings need longer runs to produce enough rings, so those
  sweeps should be repeated with a longer duration under a new protocol before
  drawing conclusions about them.
- Ten seeds per cell; node AUC is not comparable to published node-level
  benchmarks.
