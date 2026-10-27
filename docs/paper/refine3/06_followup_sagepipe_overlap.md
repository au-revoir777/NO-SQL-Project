# Amendment 2 follow-ups: SagePipe and amount overlap

This is exploratory work, declared in `docs/research/evidgnn_protocol.md` (amendment 2, commit d1cbfdb) before any run. The SagePipe selection was committed in b9a6a70 before the test blocks.

## SagePipe vs EvidPipe (block 4801–4820 × 5 = 100 paired streams)

SagePipe is the shipped pipeline plus the plain W2 GraphSAGE as a detector, scored by a fused ring scorer that uses GraphSAGE member statistics computed out of fold. Its validation selection is node threshold 0.9 and θ_a 0.7 (validation F1 0.894).

| Method | F1 | P | R | False rings/run | PR AUC |
|---|---|---|---|---|---|
| **SagePipe** | **0.859** | 0.900 | 0.835 | 0.93 | **0.915** |
| EvidPipe | 0.856 | 0.890 | 0.836 | 0.97 | 0.893 |
| GraphSAGE unscored | 0.767 | 0.872 | 0.703 | 0.78 | — |
| Hybrid | 0.762 | 0.763 | 0.803 | 2.09 | 0.813 |
| Shipped pipeline | 0.728 | 0.755 | 0.731 | 1.47 | 0.797 |

| Contrast | Δ | 95% CI | 90% CI | p |
|---|---|---|---|---|
| SagePipe − EvidPipe | +0.003 | [−0.020, 0.025] | [−0.017, 0.023] | 0.80 |
| SagePipe − GraphSAGE | +0.091 | [0.064, 0.119] | | < 0.001 |
| EvidPipe − GraphSAGE | +0.088 | [0.060, 0.117] | | < 0.001 |
| SagePipe − hybrid | +0.097 | [0.078, 0.116] | | < 0.001 |
| SagePipe − shipped pipeline | +0.130 | [0.101, 0.160] | | < 0.001 |

**Equivalence.** SagePipe and EvidPipe are equivalent at ±0.05 (the 90% CI lies inside). Per amendment 2, the paper presents the simple system: any GNN plus the GNN-aware ring scorer. EvidGNN's gate is reported as a tested and rejected design.

**EvidPipe − GraphSAGE across the three fresh blocks:** +0.102 (4001–4020), +0.088 (4101–4120), +0.088 (4801–4820).

**The hybrid has the same detectors as SagePipe but a scorer without GNN statistics.** It is 0.097 below SagePipe and level with GraphSAGE. The GNN statistics in the ring scorer are the whole difference.

## Amount overlap (block 4701–4710 × 5; benign median 2,000; all models trained on the default generator)

| Method | F1 | P | R | False rings/run | PR AUC |
|---|---|---|---|---|---|
| Rules + own scorer | 0.661 | 0.833 | 0.591 | 0.50 | 0.677 |
| Shipped pipeline | 0.641 | 0.590 | 0.755 | 3.48 | 0.680 |
| EvidPipe | 0.450 | 0.330 | 0.891 | 15.56 | 0.592 |
| SagePipe | 0.399 | 0.295 | 0.809 | 22.78 | 0.456 |
| GraphSAGE unscored | 0.000 | — | 0.000 | 0.20 | — |

- EvidPipe − shipped pipeline: −0.192 [−0.225, −0.155].
- EvidPipe − SagePipe: +0.051 [0.025, 0.080]. The gated model degrades somewhat less here; exploratory.

**Reading.** The GNN-inclusive pipelines keep recall but flood with false rings. The GNN's amount-based member probabilities push the fused scorer up on benign groups. The rule-based pipeline and the scored rules degrade least.

**Paper wording:** "The advantage needs training-like inputs."
