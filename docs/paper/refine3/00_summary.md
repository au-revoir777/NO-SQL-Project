# Round 3 and the GNN extension: summary

Branch `feat/round3-evidgnn`. Write-ups 01–06 in this folder. Protocols: `docs/research/round3_protocol.md` and `docs/research/evidgnn_protocol.md` (amendments 1–3); commit hashes are in `docs/research/PROTOCOL_LOG.md`.

## Headline (updated): AnchorPipe

AnchorPipe is a GNN pipeline with a label-free shift guard (`07_anchorpipe.md`). All three confirmatory tests are supported:

- **In distribution:** +0.099 over GraphSAGE, 95% CI [0.075, 0.123].
- **Under amount overlap:** +0.239 over the unguarded GNN pipeline.
- **Against the rule-based pipeline under shift:** non-inferior (−0.008, 90% CI [−0.018, 0.001]).

## Earlier headline

A GNN-inclusive pipeline beats every existing method on this benchmark. It adds a GNN as a detector and uses a ring scorer that reads the GNN's member probabilities, trained out of fold. Its gain over GraphSAGE, the strongest existing method:

| Block | Difference in F1 | 95% CI | Status |
|---|---|---|---|
| 4001–4020 | +0.102 | [0.067, 0.138] | Confirmatory; Holm p < 0.001 |
| 4101–4120 | +0.088 | — | Replication |
| 4801–4820 | +0.088 | — | Replication |

- **Plain GraphSAGE inside the pipeline (SagePipe) is equivalent to our gated EvidGNN version** (+0.003, 90% CI within ±0.05).
- **SagePipe is more robust to large hubs.** EvidPipe collapses from a 500-account hub upward.
- **The gate and the evidence ring rule hurt.** The confirmatory test H2 is rejected. The GNN-aware ring scorer is the contribution (+0.101 over the shipped scorer).
- **H3 (LOSO) and H4 (10% labels) are not supported.**

## Limits found this round

- **Amount shift.** With benign amounts overlapping ring amounts, the GNN-inclusive pipelines fall to 0.40–0.45 F1, below the rule-based pipeline (0.64) and the rules (0.66). GraphSAGE alone falls to 0.
- **Unseen scenario.** GraphSAGE loses 0.057 F1 when the test scenario is left out of training; the pipeline's scorer loses nothing.
- **Amount features.** The pipeline's own scorer depends on amount features: ring PR AUC drops from 0.77 to 0.55 without them.
- **Cost.** The GNN runs on the whole graph each batch. At a 10,000-account hub a stream takes about 240 s, against 11 s for the incremental pipeline.

## Round-3 review items (R1–R8)

- **R1:** the cap sweep shows every cap costs F1, including cap 27 (−0.051). The capped rules find hub-hiding rings through cycles (27) and ring-only devices or cards (14), not through the hub.
- **R2:** raw and Holm-adjusted p-values are in the text. "Preregistered" is replaced. The protocol log is added. Exploratory labels are in the abstract and conclusion.
- **R3:** the Table V constant row is defined. A step weight costs 0.041; a constant two-evidence weight differs by +0.027 (exploratory) but finds fewer adaptive rings. The "shape" wording is softened.
- **R4:** GraphSAGE LOSO and the decoy sweep are done. The PR AUC CI is +0.061 [0.007, 0.116]. Precision at matched recall is added, and hybrid hub-hiding is 89/107.
- **R5:** the amount ablation and the overlap variant are done (above).
- **R6:** latency in one environment, run alone. The incremental engine is cheaper than the 5 s timer in every seed from 5,000 users. The timer is cheaper at 1,000.
- **R7:** fixed the stale GB number note, the Table VIII references, seed blocks declared, "equivalent within 0.05 F1", and six existing methods.
- **R8:** the abstract is now about 150 words. Fixed the FRAUDAR weight (1/log(d+5)), the Ding citation wording and the IEEE-CIS link (Kaggle). The venue page limit was set aside at the user's request.

## Open items for the authors

- **Branch reset.** `feat/paper-refine` still carries three early round-3 commits; resetting it needs a force-push.
- **Archive deposit.** Deposit `docs/research/` with its commit hash (for example on Zenodo) for a timestamped record.
- **Real data.** IEEE-CIS needs a Kaggle login to download; see `docs/research/gnn/s0b_datasets.md`.
