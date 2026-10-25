# E2b and E2c results

Protocol: `docs/research/e2b_protocol.md` (committed before any result, 6749f46).
Code: 3d7ef27. Tables: `docs/research/e2b_tables.md` (generated). All three runs
(`results/e2b_tuning/`, `results/e2b_hub_heavy/`, `results/e2c_weight_functions/`)
were recorded on a clean tree (`git_dirty: false`).

## Edge thresholds (validation seeds 301-303, alert threshold 0.8)

| h(d) | Selected edge threshold | Mean validation F1 |
|---|---|---|
| 1/ln(1+d) (shipped) | 0.3 | 0.722 |
| 1/d | 0.1 (grid edge) | 0.609 |
| 1/sqrt(d) | 0.2 | 0.684 |
| soft cap at 10 | 1.0 (grid edge) | 0.644 |
| constant | 1.0 (grid edge) | 0.734 |

As the protocol requires, the grid was not extended. Three functions sit on an
edge, so they might do somewhat better with a wider grid. The constant is flat
at 0.587 for every threshold below 1.0 and jumps at 1.0. At 1.0 a pair needs
more than one fresh shared attribute, or one attribute plus transfers, so the
threshold does the work the degree discount was meant to do.

## E2b: hub_heavy, seeds 1001-1030 (30 paired runs)

| h(d) | P | R | F1 | Hub-hiding recall | p vs shipped |
|---|---|---|---|---|---|
| 1/ln(1+d) (shipped) | 0.75 | 0.88 | 0.79 | 0.87 | - |
| 1/d | 0.63 | 0.57 | 0.56 | 0.56 | <0.001 |
| 1/sqrt(d) | 0.75 | 0.87 | 0.79 | 0.83 | 0.934 |
| soft cap at 10 | 0.99 | 0.44 | 0.60 | 0.27 | <0.001 |
| constant | 0.79 | 0.87 | 0.81 | 0.83 | 0.249 (d_z -0.12) |

**Primary test (shipped vs constant).** p = 0.249. Under the decision rule, the
shipped weight's F1 advantage over a constant weight is not established. The
point estimate slightly favours the constant.

## E2c: 5 scenarios, seeds 1001-1010 (50 paired runs per function)

| h(d) | F1 | Hub-hiding recall | Holm p vs shipped |
|---|---|---|---|
| 1/ln(1+d) (shipped) | 0.73 | 0.67 | - |
| 1/d | 0.62 | 0.37 | 0.004 |
| 1/sqrt(d) | 0.74 | 0.69 | 0.504 |
| soft cap at 10 | 0.68 | 0.19 | 0.478 |
| constant | 0.76 | 0.81 | 0.478 |

## Reading

- What matters is keeping hub links. Weights that discount busy attributes
  hard (1/d) or switch them off (soft cap at 10) lose the rings hidden behind
  hubs: hub-hiding recall falls to 0.37 and 0.19 across scenarios, and to 0.56
  and 0.27 on hub_heavy.
- Within the range that keeps hub links, the shape does not matter measurably
  once each function gets its own edge threshold. 1/ln(1+d), 1/sqrt(d) and a
  constant are within noise of each other.
- The E2 ablation ("w/o hub weighting", constant at the shipped threshold 0.3)
  understated the constant, because 0.3 was tuned for 1/ln(1+d).
- Consequence for C1: it is a claim about not capping, which keeps rings behind
  hubs reachable (E3: recall 0.81 vs at most 0.53 for any cap). It is not a
  claim that the logarithmic discount is better than simpler alternatives. The
  abstract, C1, the RQ5 text (new "Weight functions" paragraph), the conclusion
  and the Tuning threat are reworded accordingly.
