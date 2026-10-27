# EvidGNN ablations (A0–A6), H2 and H4

**Setup:** block 4101–4120 × 5 = 100 paired streams. Selections from `results/evidgnn_tuning/selected.json`, the same ones used on the main block.

## Results

| ID | Variant | F1 | P | R | False rings/run | hub_heavy F1 |
|---|---|---|---|---|---|---|
| A0 | EvidGNN, gate on, evidence ring rule | 0.658 | 0.744 | 0.611 | 1.51 | 0.770 |
| A1 | EvidGNN, gate off, evidence ring rule | 0.721 | 0.837 | 0.654 | 0.87 | 0.876 |
| A2 | EvidGNN, gate on, "any" ring rule | 0.697 | 0.758 | 0.668 | 1.57 | 0.560 |
| A3 | GraphSAGE, evidence ring rule | 0.699 | 0.815 | 0.635 | 1.07 | 0.828 |
| A4 | GraphSAGE, "any" rule (baseline) | 0.755 | 0.861 | 0.700 | 0.90 | 0.663 |
| A5 | EvidPipe (fused scorer) | **0.843** | 0.875 | 0.826 | 0.97 | 0.912 |
| A6 | EvidPipe, shipped 19-feature scorer | 0.742 | 0.734 | 0.778 | 2.07 | 0.782 |

## Contrasts (Δ F1, 95% cluster bootstrap, sign-flip p)

| Contrast | Δ | 95% CI | p | hub_heavy |
|---|---|---|---|---|
| **H2:** A0 − A1 (gate on − off) | **−0.063** | [−0.084, −0.043] | < 0.001 | −0.107 |
| A0 − A2 (evidence − any rule, EvidGNN) | −0.040 | [−0.064, −0.015] | 0.036 | +0.210 |
| A3 − A4 (evidence − any rule, GraphSAGE) | −0.056 | [−0.085, −0.027] | 0.007 | +0.165 |
| A5 − A6 (fused − shipped scorer) | **+0.101** | [0.079, 0.123] | < 0.001 | +0.130 |
| A5 − A4 (EvidPipe − GraphSAGE; replication of H1) | **+0.088** | [0.053, 0.124] | < 0.001 | +0.249 |
| A2 − A4 (gated model − GraphSAGE, same rule) | −0.058 | [−0.083, −0.034] | < 0.001 | −0.103 |

## Kill criteria (declared in S3) and what they now require

- **Gate claim: dropped.** A1 is not within ±0.02 of A0; it is better by 0.063. Gating busy attributes out of message passing hurts the GNN (H2 is significant in the wrong direction). Removing busy attributes as message-passing nodes discards information a GNN can use. This mirrors the round-3 cap sweep: busy attributes help as supporting evidence.
- **Evidence ring rule: dropped as an overall gain.** It costs 0.04–0.06 F1 overall, for both models. It is a strong trade-off on hub hiding (+0.17 to +0.21 on hub_heavy) and loses on high_noise and baseline.
- **Fusion: kept.** A6 is 0.101 below A5. The GNN's member probabilities inside the ring scorer are what make the GNN-inclusive pipeline work. Adding the GNN as a detector with the shipped scorer (A6, 0.742) does not beat GraphSAGE alone (0.755).
- **Main claim: holds and replicates.** EvidPipe − GraphSAGE is +0.102 on 4001–4020 (H1) and +0.088 on 4101–4120 (A5 − A4).

**Outcome tree branch: "H1 positive, gate does not help".** The gain comes from combining a GNN with the pipeline (its candidate rings and a ring scorer that uses the GNN's member probabilities), not from gating message passing.

## H4 (label efficiency, block 4301–4310 × 5, 10% of snapshots, seed 7001)

| Model | F1 | P | R |
|---|---|---|---|
| EvidGNN (10% labels) | 0.631 | 0.730 | 0.591 |
| GraphSAGE (10% labels) | 0.653 | 0.696 | 0.663 |

H4: −0.022 [−0.071, 0.022], p = 0.49. **Null:** no label-efficiency advantage for the gated model.

Exploratory, across blocks: EvidGNN loses little from 100% to 10% labels (0.651–0.658 → 0.631), while GraphSAGE loses more (0.755–0.758 → 0.653).

## Implication: an exploratory follow-up

The gated model is worse than GraphSAGE as a node classifier (A2 − A4 = −0.058), yet the fused pipeline with it beats everything. A pipeline that fuses **plain GraphSAGE** member probabilities into the ring scorer (no gate, no evidence edges) is therefore the obvious simpler candidate. It is tested as a declared follow-up on a fresh block (amendment 2), not by re-reading these blocks.
