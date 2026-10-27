# Leave-one-scenario-out: H3 (EvidGNN) and round-3 R4 (pipeline vs GraphSAGE)

The drop for a method is F1 of its all-scenario model minus F1 of the model trained without the test scenario, paired by stream. Each scenario is tested with 20 seeds.

## Round 3 R4 (seeds 3201–3220): GraphSAGE vs the pipeline scorer

| Method | All | LOSO | Drop |
|---|---|---|---|
| GraphSAGE (t 0.95) | 0.755 | 0.698 | **0.057** [0.037, 0.078] |
| Pipeline (scorer retrained without X) | 0.661 | 0.661 | 0.001 [−0.010, 0.012] |

- **Drop(GraphSAGE) − drop(pipeline): +0.057** [0.033, 0.081], p < 0.001.
- **Per scenario:** high_noise +0.198, adversarial +0.038, drift +0.035, hub_heavy +0.013, baseline 0.

**Protocol wording (CI excludes 0):** "GraphSAGE's advantage depends on having seen the scenario in training."

The pipeline's rule stage does not depend on labels, and its scorer loses nothing when a scenario is left out.

## H3 (confirmatory, seeds 4401–4420): EvidGNN vs GraphSAGE, both unscored

| Scenario | EvidGNN all → LOSO | GraphSAGE all → LOSO |
|---|---|---|
| Adversarial | 0.375 → 0.343 | 0.446 → 0.446 |
| Baseline | 0.786 → 0.691 | 0.849 → 0.850 |
| Drift | 0.830 → 0.773 | 0.942 → 0.874 |
| High noise | 0.402 → 0.432 | 0.830 → 0.678 |
| Hub heavy | 0.820 → **0.557** | 0.722 → 0.703 |

- **Drops:** EvidGNN 0.083 [0.056, 0.111]; GraphSAGE 0.048 [0.024, 0.073].
- **H3 statistic, drop(GraphSAGE) − drop(EvidGNN):** −0.036 [−0.073, 0.000], p = 0.127. Not supported.
- **Per scenario, EvidGNN loses most on hub_heavy** when it was not trained on it (−0.26).

**Outcome-tree wording:** "Both models depend on having seen the scenario." The gated model, if anything, depends on it more.

## Confirmatory family (EvidGNN protocol, Holm over four)

| Hypothesis | Estimate | 95% CI | Raw p | Holm p | Outcome |
|---|---|---|---|---|---|
| H1 EvidPipe − strongest existing (GraphSAGE) | +0.102 | [0.067, 0.138] | < 0.001 | < 0.001 | Supported |
| H2 gate on − gate off | −0.063 | [−0.084, −0.043] | < 0.001 | < 0.001 | Rejected (gate hurts) |
| H3 drop(GraphSAGE) − drop(EvidGNN) | −0.036 | [−0.073, 0.000] | 0.127 | 0.25 | Not supported |
| H4 EvidGNN − GraphSAGE at 10% labels | −0.022 | [−0.071, 0.022] | 0.487 | 0.49 | Not supported |
