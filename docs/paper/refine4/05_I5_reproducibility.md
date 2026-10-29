# I5 — Reproducibility audit

| Item | Status | Where |
|---|---|---|
| GraphSAGE settings | Stated in full: 2 layers, hidden 64, mean aggregation over the full neighbourhood, dropout 0.2, Adam lr 0.005, weight decay 5e-4, 40 epochs, class-weighted BCE, seed 0. Also stated: the twelve node features (listed), 879 snapshots from seeds 101–110 in six scenarios, and the node-to-ring rule (connected components over shared attributes or transfers, 3–25 accounts). Each setting was checked against `src/fraudsim/detectors/external.py` and the training script | body.tex, Configurations |
| BWGNN settings | Order 2, hidden 64, lr 0.01, 100 epochs, class-weighted loss; same graph, features, snapshots and ring rule. Thetas match the authors' `calculate_theta2` | body.tex; `round4_protocol.md` |
| Peeling | FRAUDAR-style greedy peeling on users × objects, column weight 1/log(x+5), at most ten blocks per pass, tuned minimum block score | body.tex |
| Louvain / Leiden | User–user graph weighted by shared attributes and transfers; Leiden via `leidenalg` RBConfiguration, seed 0, minimum density 0.5 | body.tex |
| Deterministic GNN training | **Partly.** Training uses fixed seeds. GraphSAGE was trained with PyTorch's default two threads; later GNNs use one. Bit-for-bit retraining is **UNVERIFIED** (not tested). The paper says so, and every test result uses the saved models, which are distributed | body.tex, after Configurations |
| Windows-era tables on Linux | **Done.** 38/38 recorded rows reproduce exactly with `requirements-lock.txt`. That is 30 rows from Tables III and X (two seeds per method; digests, counts, P/R/F1) and 8 rows from the scale table (1,000 and 5,000 users, two seeds, both modes; digest, events, batches, median region). The scale table's latency columns are machine-dependent and not checked. The scenario table was not sampled separately: it is produced from the same `e1_baselines` runs | `scripts/check_reproduction.py`; body.tex, Data and code availability |
| Anonymised archive | **Done.** `scripts/make_anonymous_archive.sh` builds a zip from `git archive HEAD`. It removes the compiled PDF, `.github` and the refinement notes, and replaces names, e-mails, the repository owner and the affiliation. A final grep fails the build if any identifying string remains (verified: 0) | scripts/ |
| Availability paragraph | Matches what exists: code, simulator, protocols with commit log (`PROTOCOL_LOG.md`, now regenerated to include `anchor_protocol.md` and `round4_protocol.md`), results with stream digests, trained models, table and macro scripts, `REPRODUCE.md` (round-4 commands added), the reproduction check and the archive. The DOI is promised on acceptance, not claimed | body.tex |
| Protocol order | `round4_protocol.md` was committed at 15:31 on 2026-10-29. The first BWGNN results were committed at 16:09 and the guard results at 17:02 | git log |

## Still open

- Bit-for-bit retraining of the GNNs is untested. A future check would retrain BWGNN (one thread) and compare its weights.
- Latency is not reproducible by design. The paper reports latency only from runs made alone.
