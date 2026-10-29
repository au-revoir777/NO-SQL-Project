# Round 4 refinement — summary

| Item | File | Outcome |
|---|---|---|
| Input check, I1 novelty audit | 01_I1_novelty_audit.md | Both contributions are incremental. The hub result is reframed as an empirical finding, and AnchorPipe as GNN stacking with a rule fallback. Retitled "Keeping Hub Links: Pairwise Evidence, GNN Stacking and a Rule Fallback for Fraud Ring Detection" |
| I2 claims fixes | 02_I2_claims.md | Holm reporting fixed. Hub condition: no new run needed (validation F1 is flat across θ_e). BWGNN added: AnchorPipe +0.128 over it; GraphSAGE stays the strongest existing method tested. The key equivalences hold at ±0.03; MDE is 0.049 and 0.034 |
| I3 guard controls | 03_I3_guard_controls.md | A standard KS test on amounts matches our trigger, so the trigger is not the contribution. Under five other shifts the GNN did not fail. The oracle shows room for a better switching rule |
| I4 statistics and consistency | 04_I4_statistics_consistency.md | Three Holm families (11 tests), seed blocks, method counts, process language, latency, signs and tie wording fixed |
| I5 reproducibility | 05_I5_reproducibility.md | Configurations are stated in full. 38/38 Windows-era rows reproduce on Linux. An anonymised archive script was added. Bit-for-bit GNN retraining is untested and disclosed |
| I6 citations | 06_I6_citations.md | All 18 entries exist, with metadata fixes. Spade is qualified; BWGNN and block purging were added |
| I7 final review | 07_I7_final_review.md | Hostile review, responses, exit checklist (all pass; one disclosed gap) and the final claims ledger |

Protocol: `docs/research/round4_protocol.md` (committed before the runs). New seed blocks: 6001–6020 (BWGNN) and 6101–6165 (guard controls).
