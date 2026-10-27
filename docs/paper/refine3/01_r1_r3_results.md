# Round 3: R1 (cap sweep) and R3 (step weight): results

Protocol: `docs/research/round3_protocol.md`, committed before these runs. All tests are exploratory. Each block has 100 paired streams (20 seeds × 5 scenarios). Differences are scenario-weighted, with 95% cluster-bootstrap CIs and stratified sign-flip p-values.

## R1: degree cap inside the full pipeline (seeds 3001–3020)

| Arm | F1 | Precision | Recall | False rings/run | Hub-hiding detected |
|---|---|---|---|---|---|
| No cap (shipped) | 0.710 | 0.754 | 0.695 | 1.47 | 64/111 |
| Cap 250 | 0.710 | 0.754 | 0.695 | 1.47 | 64/111 |
| Cap 50 | 0.676 | 0.725 | 0.659 | 1.65 | 49/111 |
| Cap 27 | 0.659 | 0.707 | 0.641 | 1.67 | 39/111 |
| Cap 10 | 0.623 | 0.680 | 0.606 | 1.75 | 24/111 |
| Rules (cap 10, cycle) + own scorer | 0.620 | 0.862 | 0.533 | 0.38 | 55/111 |

No cap minus each capped arm:
- **Cap 10:** +0.087 [0.066, 0.109], p < 0.001; hub_heavy +0.240.
- **Cap 27:** +0.051 [0.035, 0.067], p < 0.001; hub_heavy +0.096, adversarial +0.083, drift +0.053.
- **Cap 50:** +0.034 [0.020, 0.049], p < 0.001.
- **Cap 250:** identical. No attribute in these streams reaches 250 users.
- **Rules + own scorer:** +0.090 [0.056, 0.124]. Per scenario: adversarial +0.229, high_noise +0.283, hub_heavy −0.025, baseline −0.047.

**Reading.**
- **Cap 27 removes exactly the attributes that cannot link a pair alone at θ_e = 0.3, and it still costs 0.051 F1.** Busy attributes therefore contribute as supporting evidence, a second piece added to a transfer or a rare attribute. They are not only harmless noise. This is the strongest form of the "keep hub links" claim.
- **The cost grows monotonically with how much of the hub tail the cap removes.**

**Paper wording (R1 outcome).** "Inside the pipeline, removing attributes above any degree cap lowers F1. This includes cap 27, which removes only attributes that cannot link a pair alone (−0.051, 95% CI −0.067 to −0.035). Hub links matter as supporting evidence."

**Rules + own scorer on hub_heavy.** The rule baseline is close to the pipeline (−0.025) and recovers 55 hub-hiding rings against 64. Its deficit is on adversarial and high-noise streams, where cap 10 plus cycles produces few candidates and its scorer cannot recover recall.

## R3: constant weight with an explicit cutoff (seeds 3101–3120)

| Arm | F1 | Precision | Recall | False rings/run | Adaptive | Hub-hiding |
|---|---|---|---|---|---|---|
| 1/ln(1+d), θ_e 0.3 (shipped) | 0.712 | 0.761 | 0.701 | 1.46 | 18/26 | 63/107 |
| step_27 (1 if d ≤ 27, else 0.2) | 0.670 | 0.727 | 0.657 | 1.56 | 13/26 | 46/107 |
| Constant, θ_e 1.0 (two pieces) | 0.738 | 0.813 | 0.711 | 1.01 | 13/26 | 69/107 |

Contrasts:
- **step_27 − shipped:** −0.041 [−0.061, −0.021], p < 0.001; hub_heavy −0.136.
- **Constant two-piece − shipped:** +0.027 [−0.001, 0.054], p = 0.089. Per scenario: adversarial −0.086, drift +0.089, high_noise +0.082, hub_heavy +0.049.

**Reading.**
- **The discount's shape matters.** A step that keeps the "rare attributes link alone" property loses to 1/ln. It does so most on hub_heavy, where the 0.2 floor lets busy attributes add up too easily.
- **The adaptive-ring gap is about solo links.** The shipped weight detects 18/26 adaptive rings against 13/26 for both other arms.
- **The two-evidence constant rule is not worse overall,** and it has fewer false rings, but it loses on the adaptive scenario.
- This agrees with the N-D result (the evidence condition, not the shape of h, carries the overall effect). It qualifies Table V's constant row: with θ_e = 1.0 the constant weight is competitive.

**Paper wording (R3).** "Matching the 'rare attributes link alone' property with a step function does not reproduce the discount (−0.041 F1). A constant weight that requires two pieces of evidence is not significantly different overall (+0.027, CI −0.001 to 0.054, exploratory) but detects fewer adaptive rings (13/26 vs 18/26). The adaptive gap therefore comes from rare attributes linking alone."
