# Prompt 2: F1 (hostile review), F2 (exit checklist), F3 (submission diff), final ledger

Paper: `docs/paper/paper.pdf` (15 pages; the original was 12), commit `c2c400a` and later on `feat/paper-refine`.

## Results the revision rests on (all on fresh, preregistered seed blocks)

| Experiment | Seeds | Result |
|---|---|---|
| R1: degree cap inside the pipeline (confirmatory) | 2001–2010 | no cap − cap 10 = **+0.084** [0.048, 0.121], p 0.002; hub-hiding 29/52 vs 9/52 |
| N-D: busy attribute may / may not suffice alone | 2401–2420 | constant: two − one = **+0.137** [0.106, 0.168]; 1/ln: two − shipped = 0.000 [−0.028, 0.028] (confirmatory, null); shape under the condition −0.008 [−0.020, 0.003] |
| W3: existing methods, own scorers (confirmatory vs strongest) | 2101–2120 | proposed 0.719; GraphSAGE 0.778 (**−0.059** [−0.097, −0.023], p 0.025); rules per-scenario +0.059; rules +0.072; Louvain +0.198; Leiden +0.212; peeling +0.263; PR AUC proposed 0.780 vs GraphSAGE + scorer 0.719 |
| W3b: pipeline + GraphSAGE (confirmatory) | 2301–2320 | hybrid 0.770 vs GraphSAGE 0.780: **−0.010** [−0.044, 0.023] (matches within 0.05); hybrid − proposed +0.052 [0.023, 0.081]; GraphSAGE − proposed replicates (+0.062) |
| R5: 10,000 users | 2501–2505 | timer > 1 s per simulated second in 5/5 seeds; incremental cheaper in 4/5 (median 185 ms), 1,270 ms in one |
| R6: grid edges | 301–303 (+ E2b/E2c streams) | 1/d moves to 0.05: −0.04 [−0.06, −0.02] vs shipped (was −0.11); constant and soft cap interior |
| R9: evidence deletion | 1001–1010 (E12 streams) | top-ranked evidence agrees with largest-drop group 0.76 (chance 0.35) = the "always transfers" baseline |

Holm over the confirmatory family of four (R1, W3, W3b, N-D):

| Comparison | Raw p | Holm p |
|---|---|---|
| R1 | 0.0018 | 0.007 |
| W3 (against us) | 0.025 | 0.075 |
| W3b | 0.66 | 1.0 |
| N-D | 0.98 | 1.0 |

W3's CI excludes 0 unadjusted. After Holm it is borderline. The paper states the CI, not "significant after correction".

## F1. Hostile review (as a skeptical PC member would write it)

> **Novelty.** The paper's surviving contribution is a design condition: keep links through busy shared attributes, but never let one such attribute link two accounts by itself. The degree discount is FRAUDAR's, the pairwise accumulation of shared-group evidence is meta-blocking's ARCS weighting from entity resolution, and incremental peeling with the same weighting is Spade's. The authors' own controls show the discount's shape is irrelevant, which makes the condition look like a sensible threshold rule rather than a method. The system parts (dirty-region recomputation, logistic regression with isotonic calibration, linear explanations) are standard, and the authors now say so.
>
> **Evidence.** All positive results come from a simulator written by the same authors who wrote the detector and the evasion strategies. On that simulator, a plain GraphSAGE classifier trained on ring labels beats the proposed pipeline (0.78 vs 0.72 F1; the gap replicates on a second seed block). Combining the two only matches GraphSAGE. The pipeline wins against rule, community and peeling baselines, but those are the authors' reimplementations configured to emit the authors' ring object. The isolation experiments are well designed, but they establish a property of this generator. There is no real-data test of the central mechanism, because no public data has shared-attribute links with ring labels.
>
> **Soundness and reproducibility.** The statistics are now careful: fresh seed blocks per experiment, protocols committed before runs, cluster bootstraps, a declared equivalence margin, and per-method scorers. Remaining concerns:
> - the equivalence margin (0.05 F1) was chosen by the authors after seeing some intervals;
> - the GraphSAGE baseline is a single architecture with fixed training settings, against a pipeline with years of tuning;
> - revision timings come from a shared 2-core container;
> - ring-level exactness of the incremental engine fails at large hubs.
>
> Reproducibility is good (lockfile, regeneration scripts, snapshot checks) apart from the missing archival DOI.
>
> **Strongest reason to reject:** on the authors' own benchmark, a standard GNN baseline outperforms the proposed pipeline, and what remains is a design guideline whose novelty over FRAUDAR and meta-blocking is thin and which is untested on real data.

### How the paper now answers each point, and what is open

| Point | Current answer | Open |
|---|---|---|
| Novelty thin (FRAUDAR, meta-blocking, Spade) | Related Work names all three; C1 is stated as a condition with isolation controls showing *which* part matters (cap −0.08; one-attribute-suffices −0.14; shape ±0.01), which neither FRAUDAR nor meta-blocking reports for fraud rings | Whether a venue accepts a measured design condition as a contribution. Prior-art searches were not exhaustive (VERIFY meta-blocking details) |
| GNN outperforms | Reported in abstract, Table V, conclusion; mechanism: drift and noise precision; pipeline better on ranking (PR AUC), adaptive and decoy rings; hybrid matches GNN with higher recall | No claim of superiority over learned methods survives. If the paper must claim "beats existing methods", it can only do so for non-learned methods |
| Synthetic only | Stated in abstract and Threats; circularity sentence added | Real data with shared-attribute links (IEEE-CIS without ring labels is the closest) |
| Reimplemented baselines | Threats (Baselines); code public; Spade output reproduced, not latency | Run Spade's C++ for latency; a second GNN (e.g. temporal) |
| Margin chosen after seeing CIs | Justified independently (one ring per two to four runs); all 90% CIs reported | The reader can apply another margin |
| Timings on a shared container | Revision runs not used for latency, except R5 (re-run alone) | Laptop re-run of R5 for consistency with Table IV |
| Exactness fails at large hubs | Pair-level condition stated; ring-level failure and both causes reported in §III-C and RQ3 | A restriction-stable extraction step would be needed for a guarantee |
| Explanations | Deletion test reported honestly: ranking no better than "always transfers" | Multi-feature or ring-level explanations |
| No DOI | Availability paragraph promises it at camera-ready | Create the release |

## F2. Exit checklist

| Item | Pass / fail |
|---|---|
| Ledger has no unsupported claim in abstract or conclusion | **pass** (final ledger below) |
| Every retained contribution passes the six-part novelty test | **partial**: C1′ passes 1–4 and 6; 5 (prior art) partial pending VERIFY items. System and evaluation are no longer listed as contributions |
| Every win names its attributed element | **pass**: the scorer (Table II), pairwise multi-detector pipeline vs rules (noise), keeping hub links (hub hiding), the combination (hybrid) |
| All comparisons scored-vs-scored or labelled | **pass**: Table V own scorers; unscored comparisons labelled (Figs. 6–8 captions, Table II/III with text pointers) |
| Per-method scorers, or limitation disclosed | **pass** (Table V); the shipped-scorer limitation stays disclosed for Table II |
| Fresh seeds untouched until the final run | **pass**: each block 2001–2010, 2101–2120, 2301–2320, 2401–2420, 2501–2505 used once, after a committed protocol. Process amendments (two late commits caused by `.gitignore`; R5 re-run) recorded |
| Equivalence tests for "no difference" claims | **pass**: δ 0.05, 90% CIs reported; "equivalent" used only where the CI lies inside |
| Stats family and Holm count stated | **pass**: §IV-B (family of four); Table II and VIII captions |
| Reproducibility checklist complete | **pass with open items**: DOI release; dev tools unpinned; seeds as module constants |
| Threats covers synthetic-only, single-laptop timing, white-box attacker, GNN, calibration | **pass**. GNN covered as run and as outperforming; white-box attacker spec in `07_refinement.md` |
| All VERIFY marks resolved | **fail**. Open: FRAUDAR KDD passage, Leiden DOI, Liben-Nowell DOI, meta-blocking bib details, IEEE-CIS URL, Spade public code URL, Zenodo integration. All are bibliographic or URL checks needing a browser |

## F3. Submission diff (by section)

| Section | Edits |
|---|---|
| Title | "Keeping Hub Links: Pairwise Evidence for Fraud Ring Detection on Streaming Transaction Graphs" |
| Abstract | Rewritten: cap framing corrected; R1/N-D attribution; existing-method comparison including GraphSAGE and the hybrid; limits |
| Keywords | "hub-aware weighting, explainability" → "pairwise evidence, graph neural network baselines" |
| I. Introduction | Hub-dilemma paragraph (both failure modes); contributions → one contribution (the condition) + system + evaluation |
| II. Related Work | GraphSAGE; Spade's identical-sequence property and the difference from our setting; Charikar replaces DP k-core citation; Leiden replaces DP-Louvain; Liben-Nowell replaces Varma; meta-blocking paragraph |
| III-B | Renamed; the condition stated (busy attribute cannot suffice alone at θ_e 0.3) |
| III-C | Pair-level condition (k·h(251)); bound rule; ring-level equality fails (peeling not local) |
| III-D | Scorer hold-out naming; unit definition; LOSO table; counterfactual "where one exists" |
| Fig. 2 caption | Snapshot and ring-level AUCs; scorer hold-out |
| IV-B | Seed blocks; statistics (zsplit, cluster bootstrap, sign-flip, Holm family of four, δ 0.05, n ≤ 5 as ranges) |
| IV-D | Fair-comparison paragraph |
| IV-E | Revision container; lockfile; version dependence |
| V-A | Shipped-scorer caveat; Holm family for p = 0.034; per-scenario sentence with hub_heavy; Fig. 4 text (cap-independence, oracle operating point, recall CIs) |
| **V-B (new)** | Comparison with existing methods (Table V), hybrid |
| **V-C (new)** | What the advantage depends on (Table VI) |
| RQ2 | Timer wording; 10,000-user point; non-monotonic cost hypothesis; Table IV caption |
| RQ3 | Hub size with scored rules; large hubs (both causes; constant mechanism corrected; scored rules); Fig. 7 caption fixed; adaptive attacker with interval |
| RQ4 | Fig. 8 caption (unscored labelled; scored ranges) |
| RQ5 | Hub-weighting ablation heterogeneity; widened grids (1/d result); equivalence statements |
| VI RQ7 | Citation of the ring-level refit corrected; refit seeds named |
| VI RQ8 | Deletion test results replace "We have not run it" |
| VII Threats | Circularity; seed reuse; region exactness; revision timing; baselines (all run, GNN ahead); explanations; reproducibility |
| VIII Conclusion | Rewritten |
| Data and code availability | New paragraph |
| Tables (generated) | `tab5_existing.tex`, `tab6_attribution.tex`, `tab_loso.tex`, `numbers_refine.tex`; captions of Tables II, IV, VIII updated in `latex_export.py` (numbers unchanged, verified by snapshot) |

Remaining `[PENDING RESULT]` markers in the paper: **none**.

Remaining work that is not a pending result:
- the VERIFY items (F2);
- page count (15 pages vs a typical 6–8-page IEEE conference limit): check the venue's limit and cut, e.g. move §VI or the public-data section to an appendix;
- the white-box attacker (spec only);
- the DOI release.

## Final claims ledger (abstract and conclusion)

| Claim | Type | Evidence (seeds) | Strongest comparator | Attributable to | Status | Wording in paper |
|---|---|---|---|---|---|---|
| Rule detectors suppress busy attributes with a degree cap | context | — | — | — | supported | abstract, sentence 2 |
| Degree cap costs 0.08 F1 and most hub-hiding rings, within the pipeline | mechanism | R1 (2001–2010) | same pipeline with cap | keeping hub links | **supported** | abstract, C1, V-C |
| A weight letting one busy attribute suffice costs 0.14 | mechanism | N-D (2401–2420) | same pipeline, constant two-evidence | the condition | **supported** | abstract, C1, V-C |
| Given the condition, discount shape makes no difference | non-inferiority | R1, N-D (−0.008 [−0.020, 0.003]) | constant weight | — | **supported** (equivalent within 0.05) | abstract, C1 |
| Improves on rules, Louvain, Leiden, FRAUDAR peeling by 0.059–0.263 | superiority | W3 (2101–2120) | rules per scenario, own scorer | pipeline (pairwise evidence + detectors + scorer) | **supported** (exploratory contrasts, CIs exclude 0) | abstract, V-B, conclusion |
| GraphSAGE reaches higher F1 (0.778 vs 0.719) | (against us) | W3, replicated W3b | — | — | **supported** | abstract, V-B, conclusion |
| Pipeline ranks rings better, finds more adaptive and decoy rings | superiority (secondary metrics) | W3 PR AUC 0.780 vs 0.719; adaptive 24/28 vs 18/28; decoy 50/59 vs 37/59 | GraphSAGE | pipeline | **partly** (no intervals on the counts) | abstract, V-B |
| Hybrid matches GraphSAGE | equivalence | W3b (2301–2320) | GraphSAGE | combination | **supported** (CI within ±0.05) | abstract, V-B |
| Incremental: pair-level condition; ring-level equality only for small hubs; cheaper than timer at scale in most seeds | exactness / efficiency | E5b traces; E4b; R5 | timers | engine | **supported as stated** (ranges, no p-values) | conclusion |
| Slow and rotating rings rarely found; explanations describe the model; synthetic only | limitation | W3 counts; R9; — | — | — | **supported** | abstract, conclusion |
| Same rings on Neo4j / Redis | equivalence | E8 52/52 | — | — | **supported** | conclusion |
