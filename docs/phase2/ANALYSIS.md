# Phase 2 analysis: novel additions to raise credibility and appeal

Status: planning document, written 2026-10-22. Review started on branch
`feat/m8-experiments`; during writing the M9 session switched the checkout to
`feat/m9-quality` and began editing `numbers.tex`, the paper tables, README,
Makefile and compose files. The numbers below are from the files as read at the
start (M8 state); re-check them against `numbers.tex` once M9 lands. Nothing in
the repository was changed to produce this document apart from adding
`docs/phase2/`.

Ground rules used here:
- Every number about **this project** is copied from a file in the repo, and the
  file is named next to it. No new runs were made for this document.
- Every number about **another paper** is that paper's own reported value,
  attributed to it. These are not our results and are not comparable to ours
  unless stated.
- Anything that is my judgement rather than a fact is marked **[assumption]**
  or **[judgement]**.

---

## 0. Sources reviewed

| What | Where |
|---|---|
| Specification | `master_prompt.md` |
| Project state, results summary | `README.md`, `REPRODUCE.md`, `docs/*.md` |
| Paper (IEEE conference template) | `docs/paper/paper.tex`, `docs/paper/sections/{abstract,body,results,public}.tex`, `docs/paper/paper.pdf` |
| Generated numbers | `docs/paper/tables/numbers.tex` (macros generated from `results/*/results.csv`) |
| Experiment outputs | `results/e1_baselines` … `results/e7_adaptivity`, `results/public`, `results/tuning` |
| Test reports | `docs/reports/m2…m8_test_report.txt` |
| Code layout | `src/fraudsim/*`, `web/`, `tests/`, `configs/scenarios/*.yaml`, `docker-compose.yml`, `Makefile` |
| Demo | `demo/story.html` (114 KB, offline replay), `demo/PR_BODY_*.md` |
| Uploaded papers | `papers_nosql/` (76 PDFs + `citations.docx`); `images/papers_nosql/` holds an identical copy (same file list) |
| IEEE template | `papers_nosql/grfzhhncsfqn.pdf` is the IEEE conference LaTeX template instructions ("Conference Paper Title*"); not a research paper |
| Bibliography | `docs/paper/references.bib` (31 entries; uncommitted edits in the working tree) |

Paper metadata (venue, year, DOI) was taken from each PDF's embedded metadata
(`pdfinfo` Subject field) and cross-checked against `citations.docx`. Where the
two disagree, the PDF wins. Methods, datasets and metrics come from each paper's
abstract and experimental section as extracted with `pdftotext`; the
non-fraud-domain papers were read at abstract level only, and their rows say so.

---

## (a) Current state and honest limitations

### What is implemented (from code and docs)

| Component | Implemented | Source |
|---|---|---|
| Deterministic streaming simulator: benign users, heavy-tailed transactions, benign hubs (office wifi, carrier NAT, kiosks, family devices), ring lifecycle SPAWN/GROW/ACTIVE/MUTATE/DISSOLVE | yes | `src/fraudsim/simulator/`, `docs/simulator.md`, `src/fraudsim/types.py` |
| Ring types: shared_device, shared_card, shared_ip, money_cycle, smurfing_fan_in, smurfing_fan_out, layered_chain, mixed_attribute | yes | `src/fraudsim/types.py` (`RingType`) |
| Evasion: hub_hiding, low_and_slow, identity_rotation, decoy_edges, adaptive attacker | yes | `configs/scenarios/adversarial.yaml`, `tests/test_simulator.py` |
| Scenarios: baseline, high_noise, hub_heavy, adversarial, scale_sweep, drift, demo_story | yes | `configs/scenarios/` |
| Event bus: asyncio queue, Redis Streams optional | yes | `src/fraudsim/stream/event_bus.py` |
| Stores: Neo4j 5.26 + GDS, and an in-memory store with the same contract | yes | `src/fraudsim/graph/`, `docker-compose.yml` |
| Detectors: StaticCypherBaseline (Q1–Q4b), hub-aware shared attribute, temporal cycle, smurfing, community (GDS Louvain/WCC), ensemble tracker with stable ids and hysteresis | yes | `src/fraudsim/detectors/` |
| Incremental dirty-region detection vs full recompute | yes | `src/fraudsim/detectors/engine.py`, `fraudsim compare-latency` |
| Calibrated scorer (logistic regression default, gradient boosting comparison), 19 ring features | yes | `src/fraudsim/scoring/features.py` (`FEATURE_NAMES`), `docs/scoring.md` |
| Explanations: contributions, templated reason, evidence subgraph JSON, counterfactuals (feature threshold + hub-aware rule), calibration bucket | yes | `src/fraudsim/scoring/explanations.py` |
| Early-warning scoring | yes (code + a CSV column) | `src/fraudsim/scoring/early_warning.py`; column `early_warnings_before_activation` in `results/e1_baselines/results.csv` |
| Analyst feedback (`AlertPolicy`: per-ring-type threshold moves on confirm/dismiss, logged) | yes | `docs/scoring.md` §Analyst feedback, `POST /rings/{id}/feedback` |
| Metrics: ring/user P/R/F1, Jaccard matching, miss reasons, time-to-detect, latency percentiles, precision@10, PR-AUC, alerts/hour, Prometheus `/metrics` | yes | `src/fraudsim/metrics/`, column list of `results/e1_baselines/results.csv` |
| Structured logs, hash-chained audit, deterministic replay | yes | `src/fraudsim/logging/`, `fraudsim replay`, `fraudsim audit-verify` |
| FastAPI + WebSocket API (25 routes incl. `/runs/*`, `/rings/*`, `/graph`, `/oracle`, `/metrics`, `/ws`) | yes | `src/fraudsim/api/main.py` |
| React + Vite + Cytoscape + Recharts dashboard (7 components, ~1.4k lines) | yes | `web/src/` |
| Offline animated story replay | yes | `src/fraudsim/demo/story.py`, `demo/story.html` |
| Experiment suite E1–E7, tuning, stats (mean, 95% CI, paired Wilcoxon), figures, LaTeX tables | yes | `src/fraudsim/experiments/`, `results/` |
| Public-data loaders: AMLworld, Elliptic, AMLSim, PaySim (loader only) | yes | `src/fraudsim/datasets/`, `docs/datasets.md` |
| CI (GitHub Actions) | **in progress**: no `.github/` when this review started; the M9 session has since added an untracked `.github/` and `docs/HOWTO.md` on `feat/m9-quality` (not reviewed here) | repo root, `git status` |
| GNN / embedding baseline (M8 stretch, "advanced additions" 1) | **no** (no GraphSAGE/Node2Vec/FastRP in `src/`) | `grep` over `src/` |
| Privacy-preserving identifiers ("advanced additions" 3) | **no** (no salting/pseudonymisation code found) | `grep` over `src/` |
| Concept-drift detection with hub-weight refit ("advanced additions" 2) | **no** (drift scenario exists, no detector/refit) | `configs/scenarios/drift.yaml`, `src/` |

### What is measured (real numbers, with sources)

All from `docs/paper/tables/numbers.tex` (generated from the CSVs named in its
comments) unless another file is named.

| Result | Value | Source |
|---|---|---|
| E1, 5 scenarios × 10 test seeds, 300 runs: proposed ring P / R / F1 | 0.76 / 0.74 / 0.73 ± 0.05 | `results/e1_baselines/results.csv` |
| Proposed with a-priori thresholds, F1 | 0.68 ± 0.05 | same |
| Static Cypher cap 10 / cap 100, F1 | 0.21 / 0.19 (precision 0.14 / 0.12, recall 0.61 / 0.61) | same |
| Louvain, F1 | 0.29 | same |
| Connected components, recall | 0.00 | same |
| Significance | every baseline below proposed, paired Wilcoxon p < 0.001 | `README.md` Results, `docs/paper/sections/results.tex` |
| Recall by evasion (proposed) | none 91/110, decoy_edges 22/27, hub_hiding 35/52, adaptive 9/11, identity_rotation 4/14, low_and_slow 3/13 | `numbers.tex` (`\EvProp*`) |
| E3 frontier, shared-attribute rings only, with scorer: max recall cap vs hub weighting | 0.53 vs 0.81 | `results/e3_frontier/results.csv` |
| E3 best F1 with scorer: cap vs hub | 0.55 vs 0.58; at low recall the cap is more precise (0.72 at recall 0.45) | same |
| E4 scale, 100,000 users: incremental vs full per batch | 36.1 ms vs 22,501 ms | `results/e4_scale/results.csv` |
| E2 ablation F1 (full 0.72): no scorer / no hub-aware / no cycle / no smurfing / no hub weight / no time decay / no hysteresis / no incremental | 0.39 / 0.36 / 0.64 / 0.65 / 0.60 (p = 0.161) / 0.75 (p = 0.277) / 0.70 (p = 0.154) / 0.72 (identical rings) | `results/e2_ablations/results.csv` |
| E5 hub size 5→200: hub-hiding recall proposed vs cap 10 | 71/90 vs 65/90; F1 0.80 vs 0.31 | `results/e5_hub_size/results.csv` |
| E6 event rate 10→100 ev/s: proposed F1, batch latency | 0.61→0.43, 10.1→74.5 ms | `results/e6_sweeps/results.csv` |
| E7 adaptive attacker on/off: rings found | 18/22 vs 9/11 | `results/e7_adaptivity/results.csv` |
| Public data, AMLworld 4-day slice, 1 h window: laundering groups matched | 0 of 55; account precision 0.03, recall 0.01 | `results/public/results.csv` |
| Elliptic, AMLSim samples | 0 flags | same |
| Scorer snapshot-level test metrics (LR / GB) | ROC AUC 0.982 / 0.998, PR AUC 0.908 / 0.988, Brier 0.046 / 0.015, ECE 0.029 / 0.011 | `docs/scoring.md` |
| LR calibration caveat | 0.8–0.9 bucket was fraud 67% of the time on test seeds | `docs/scoring.md` |
| Single demo run `00434da7845b` (seed 7) | hub-aware 3/3 rings, 2 false rings; cap 10 2/3 rings, 23 false rings | `README.md` Offline demo |
| Tests | M8 report: 152 passed, 12 deselected; README: 159 passing at M7 including Neo4j/Redis integration tests | `docs/reports/m8_test_report.txt`, `README.md` |

### Honest limitations (what a reviewer will raise)

1. **All positive results are synthetic.** The paper says so
   (`docs/paper/sections/body.tex`, Threats to Validity: simulator realism,
   synthetic labels, tuning on the same generator).
2. **Hub-aware weighting is untested on real data.** None of the public
   datasets has device/card/IP links (`docs/datasets.md`, `README.md` Known open
   items). On AMLworld the transaction rules found 0 of 55 groups.
3. **Latency numbers are in-memory only.** "Neo4j adds query and transport cost
   that we did not include" (Threats to Validity, Latency). Redis Streams is
   implemented but no experiment in `results/` reports Redis end-to-end latency.
4. **No learned graph baseline.** Threats to Validity, Baselines: "We do not
   compare with GNN classifiers". Most 2020+ fraud papers uploaded are GNNs.
5. **Explanation quality is not evaluated.** The spec's RQ4 is explanation
   quality (`master_prompt.md`); the paper's RQ4 became sensitivity
   (`results.tex` §RQ4). Counterfactuals are generated but never checked for
   validity, stability or consistency.
6. **Calibration is reported only at snapshot level** (`docs/scoring.md`), and
   the doc notes the LR model is overconfident in middle buckets. Ring-level
   alert calibration is not reported in the paper.
7. **Evasion limits.** identity_rotation (4/14) and low_and_slow (3/13) defeat
   every method (`numbers.tex`). Decoy-edge strength is not swept (E6 sweeps
   rate, ring size and window only).
8. **Time decay and hysteresis show no significant effect** on 60–90 s
   scenarios (`results.tex` §RQ5); their value on long streams is untested.
9. **Analyst feedback loop exists but is not evaluated** (no experiment in
   `results/` uses it).
10. **Early warnings are counted but not reported** (column exists in
    `results/e1_baselines/results.csv`; no macro in `numbers.tex`).
11. **Scale stops at 100,000 users** on a 7.7 GB laptop; 10^6 was not feasible
    (`README.md`, Threats to Validity).
12. **Product surface is a research dashboard**, not an analyst tool: no auth,
    no case management, no reports, no persistence of analyst work beyond the
    audit log (`web/src/`); CI is being added by M9.
13. **Paper hygiene**: `[cite: ...]` placeholders remain and bibliography entries
    must be checked (`README.md` Known open items). The working tree shows
    uncommitted edits to `references.bib` and paper sections (M9 session).

---

## Papers: kept (2020 or later) and excluded

### Excluded (published before 2020)

| File | Year, venue (from PDF metadata) |
|---|---|
| A_Booster_Analysis_of_Extreme_Gradient_Boosting_for_Crop_Classification_using_PolSAR_Imagery | 2019, Agro-Geoinformatics |
| A_Visualization_Approach_for_Frauds_Detection_in_Financial_Market | 2009, Information Visualisation (IV) |
| Adapted_K-Core_Decomposition_and_Visualization_for_fMRI_Connectivity_Networks | 2018, IEEE EMBC |
| An_Incremental_Community_Detection_Method_in_Social_Big_Data | 2018, BDCAT |
| Hybrid_virtual_network_embedding_with_K-core_decomposition_and_time-oriented_priority | 2012, ICC |
| Hybrid_virtual_network_embedding_with_K-core_decomposition_using_path_splitting | 2014, ICCCT |
| Identification_of_key_transmission_lines_in_power_grid_using_modified_K-core_decomposition | 2013, EPECS |
| Incremental_Community_Detection_in_Social_Networks_Using_Label_Propagation_Method | 2018, FRUCT |
| Manifold-based_incremental_community_detection_method_for_online_speaker_identification | 2018, ISCSLP |
| Node-Grained_Incremental_Community_Detection_for_Streaming_Networks | 2016, ICTAI |
| Parallel_k-Core_Decomposition_on_Multicore_Platforms | 2017, IPDPSW |
| Quick_Community_Detection_of_Big_Graph_Data_Using_Modified_Louvain_Algorithm (two identical copies) | 2016, HPCC/SmartCity/DSS |
| Scalable_K-Core_Decomposition_for_Static_Graphs_Using_a_Dynamic_Graph_Data_Structure | 2018, IEEE BigData |
| Sparsifying_and_sampling_of_large_graphs_for_efficient_dense_subgraph_detection | 2016, BigComp |
| The_K-Core_Decomposition_and_Visualization_of_Internet_Router-Level_Topology | 2009, CSIE |
| Using_Extreme_Gradient_Boosting_to_Detect_Glottal_Closure_Instants_in_Speech_Signal | 2019 (the PDF's own text says "2019 IEEE"; no metadata) |
| Volume-Based_Large_Dynamic_Graph_Analytics | 2018, IV (PDF has no extractable text) |
| `grfzhhncsfqn.pdf` | not a paper: IEEE conference template instructions |

Borderline, **kept**: *Using K-core Decomposition on Class Dependency Networks
to Improve Bug Prediction* is IEEE TSE vol. 47 no. 2, Feb 2021 (DOI is from
its 2019 early-access record). *Enhancing Traffic Prediction with Interpretable
Community Embeddings via Louvain* appears twice (identical files); counted once.

`citations.docx` also contains entries that are only proceedings titles with
no paper title ([27], [31], [37], [40], [41], [42], [47], [48], [52], [53],
[58], [59]); they map to the files above or to the excluded list and should
not be used as references as written.

### Kept, core relevance (fraud / AML / graph fraud / streaming)

| # | Title | Authors | Year, venue | Core method | Datasets | Metrics reported | Idea to borrow | In our `references.bib`? |
|---|---|---|---|---|---|---|---|---|
| K1 | GB-FRD: Graph-Based Fraud Ring Detection in P2P Payment Networks | P. Pan | 2025, ICCVDM | GNN + Node2Vec embeddings on a user transaction graph; "real-time" dynamic graph | OGB, GITA, a "Fraud e-commerce" corpus, a software-failures set, ULB credit-card (284,807 txns, 492 frauds), as listed in its §IV-A | Precision, recall, F1, AUC, training time | Node2Vec embedding as an extra ring feature; also a cautionary point: none of its listed datasets carries ring labels, so ring-level ground truth is a differentiator for us **[judgement]** | yes (`pan2025gbfrd`) |
| K2 | Behavioral graph fraud detection in E-commerce | H. Yin et al. | 2022, ICDMW | Replaces "hard links" (same device/IP/card) with behavioural-similarity "soft links"; GPU HDBSCAN to drop over-concentrated nodes; unsupervised GNN embeddings | Internal e-commerce business data | ROC-AUC, PR-AUC | Its stated problem (over-linkage via widely shared IPs, sparse linkage via devices) is exactly our hub problem; motivates a soft-link edge type and an over-concentration filter as a comparison | yes (`yin2022behavioral`) |
| K3 | A Robust Graph Fraud Detection Model Based on Adversarial Reweighting | Z. Liu, J. Gao, H. Yu, X. Luo | 2025, IEEE TCSS 12(6) | Adversarial reweighting of neighbours and of training nodes against camouflage and label noise | YelpChi, Amazon, T-Finance, T-Social | AUC, F1-macro, G-Mean | Camouflage (fraud linking to benign nodes) = our decoy_edges; motivates a decoy-strength sweep and label-noise robustness for the scorer | yes (`liu2025robust`) |
| K4 | HHGFD: Graph Fraud Detection Through Heterogeneity and Heterophily Characterization | P. Hu, Y. Qin, J. Wu, Z. Yang | 2025, ICTAI | RL-driven dynamic grouping + node- and relation-level attention on heterogeneous graphs | YelpChi, T-Finance, T-Social, Elliptic | AUC (and others in tables) | Relation-level weighting: per-attribute-type learned weights instead of one hub formula for device/card/IP | yes (`hu2025hhgfd`) |
| K5 | Multi-Scale Adaptive Neighborhood Awareness Transformer for Graph Fraud Detection (MANDATE) | J. Lv, Q. Du, Y. Zhang, Y. Han, S. Li | 2026, ICASSP | Graph transformer with multi-scale positional encoding, separate homophilic/heterophilic embeddings, multi-relation fusion | YelpChi, Amazon, T-Finance | AUC, F1 | Multi-relation fusion is the learned analogue of our shared device/card/IP projection | yes (`lv2026mandate`) |
| K6 | Dual-channel Heterophilic Message Passing for Graph Fraud Detection (DHMP) | W. Zhang, J. Zhong, G. Yao, R. Han, X. Lin, L. Jiang, Z. Zhang, C. Luo | 2025, IJCNN | Splits graph into homophilic/heterophilic subgraphs, dual-channel message passing | YelpChi, Amazon, FDCompCN | AUC, F1-macro | Another heterophily-aware GNN candidate for a learned baseline; code public (per paper) | **no** |
| K7 | Adaptive Gaussian Mixture Model with Hierarchical Propagation for One-Class Graph Fraud Detection (OC-GFD) | X. Li et al. | 2025, ICME | One-class GNN trained on normal nodes only + adaptive GMM | Yelp, Amazon | AUC, G-Mean, F1 | One-class training avoids needing fraud labels; a fair learned baseline when only benign data is trusted | yes (`li2025ocgfd`) |
| K8 | Suspicious: a Resilient Semi-Supervised Framework for Graph Fraud Detection | B. Giles, B. Jeudy, C. Largeron, D. Saboul | 2023, ICTAI | Two graph auto-encoders (normal / suspicious) robust to mislabelled training nodes | Attributed networks incl. Reddit, Amazon (code + data released) | AUC under injected label noise | Evaluate our scorer and feedback loop under noisy analyst labels | yes (`giles2023suspicious`) |
| K9 | IN-GFD: An Interpretable Graph Fraud Detection Model for Spam Reviews | H. Yu, W. Liu, N. Zhu, P. Li, X. Luo | 2024, IEEE TAI 5(10) | Interpretable GFD: loss on the feature-embedding matrix + score-difference threshold that yields evidence | Four public review datasets incl. Yelp, Amazon | F1, macro-F1 | Threshold-based, quantifiable explanation evidence; supports an explanation-quality section | yes (`yu2024ingfd`) |
| K10 | One-Class Adversarial Fraud Detection Nets With Class Specific Representations (CS-OCAN) | H. Peng, J. Zhao, L. Li, Y. Ren, S. Zhao | 2023, IEEE TNSE 10(6) | Autoencoder + complementary GAN one-class model | UMD Wikipedia, credit-card fraud | AUC, F1 | Same as K7; tabular one-class baseline for ring features | yes (`peng2023csocan`) |
| K11 | Ensembles or Graph Neural Networks? Detecting Illicit Bitcoin Transactions Under Temporal Drift | S. Badjie, A. A. Susom, B. D. Sarker, N. bin Sharif, S. A. Ashraf | 2026, ICSCSA | RF/boosted ensembles vs GCN, GraphSAGE, GAT and a hybrid, temporal split | Elliptic | Illicit-class F1 (paper reports tuned RF 0.811 vs best GNN 0.582; all models fall to ≈0 after time step 43) | Time-aware evaluation; a tabular ensemble is a strong baseline; drift dominates model family | yes (`badjie2026ensembles`) |
| K12 | Temporal-Aware Graph Attention Network with XGBoost Ensemble for Blockchain Transaction Fraud Detection | R. N. Kumar, N. Oláh | 2026, CITDS | Ten models incl. five GNNs, temporal GAT, GAT+XGBoost hybrid; strict temporal splits; balanced and imbalanced | Elliptic, Ethereum phishing | F1, ROC-AUC, PR-AUC | Same lesson as K11: XGBoost baseline + temporal splits + report imbalanced setting | yes (`kumar2026tagat`) |
| K13 | LAGCN-AD: An LSH-Attention-Based GCN for Blockchain Anomaly Detection | B. Lu, T. Xiao, Y. Zhao, L. Su | 2026, ICETCI | LSH feature attention + 4-layer GCN + SMOTE + focal loss | Elliptic | Precision, recall, F1 | Imbalance handling for any learned baseline | yes (`lu2026lagcn`) |
| K14 | Research on Blockchain Anomalous Behavior Detection Technology | X. Sheng, A. Li, F. Sun | 2024, SPIC | Transformer + ResNet on time series, RF feature selection | Elliptic (augmented by crawling) | F1 and others | Low **[judgement]**: transaction-level classifier; little to borrow | **no** |
| K15 | Advanced Machine Learning Models for AML | S. B. Shah | 2025, SATC | Classical ML + MLP comparison | Elliptic (203,769 txns, 166 features) | Accuracy, precision, recall, F1 | Low; shows the common transaction-level framing we contrast with | yes (`shah2025aml`) |
| K16 | Calibration-Aware Gradient Boosting With Temporal Behavioral Features for AML | T. Azbergen, A. Tleubayeva, A. Aituov | 2026, SIST | CatBoost/XGBoost + Platt/isotonic calibration; rolling 1/7/30-day behavioural features | IBM AML (AMLworld) synthetic, ~7M txns | AUPRC, AUROC, Brier, reliability curves, Precision@Top-k, Lift@Top-k | Ring-level calibration metrics and operational Lift@k; rolling-window features for AMLworld replay | yes (`azbergen2026calibration`) |
| K17 | Real Time Fraud Detection in Digital Transactions Using ML Techniques | R. K. Parida et al. | 2026, ASSIC | SMOTE + XGBoost/CatBoost/LightGBM hybrid ensemble + SHAP | Kaggle online payment fraud (~1.29M train / 555k test) | Accuracy, precision, recall, F1, ROC-AUC | SHAP-style local/global explanation presentation in the UI | yes (`parida2026realtime`) |
| K18 | A Hybrid Isolation Forest and Deep Learning Model for Anomaly Detection in Financial Transactions | U. Anand, R. K. Singh, Y. Singh, A. K. Sharma | 2026, IC-ICNS | Isolation forest + deep model | ULB credit-card (Kaggle) | ROC-AUC, F1 | Unsupervised anomaly score as a cheap ring feature/baseline | **no** |
| K19 | Enhancing the security of financial transactions in Blockchain by using ML | D. Boughaci, A. A. K. Alkhawaldeh | 2020, SMART-TECH | Position/overview paper with ML classifiers | not recorded (overview) | not recorded | Low | **no** |
| K20 | HYADES: Adaptive Consumer Tuning in Redis Streams via Hybrid Expert Selection | K. Bora, E. Kartsakli, E. Q. Moreno | 2026, IEEE CLOUD | RL + supervised experts, bandit selector tuning Redis Streams consumer params (fetch batch, block timeout, ack batching, reclaim) | Redis Streams workloads 200–20,000 msg/s, 4–16 shards, failure injection | Consumer lag (avg/peak), throughput, latency | Measure our Redis Streams path (batch size, block timeout, consumer lag) end to end; possibly a simple adaptive batch size | yes (`bora2026hyades`) |

### Kept, method relevance (dense subgraphs, cores, communities, similarity)

| # | Title | Authors | Year, venue | Core method | Datasets | Metrics | Idea to borrow | In bib? |
|---|---|---|---|---|---|---|---|---|
| K21 | Unified Dense Subgraph Detection: Fast Spectral Theory Based Algorithms (GENDS / SpecGDS / GepGDS) | W. Feng, S. Liu, D. Koutra, X. Cheng | 2024, IEEE TKDE 36(3) | Unified densest-subgraph framework, spectral + greedy algorithms | 40 real networks up to 1.47B edges | Density quality, runtime, speedup | Weighted densest-subgraph as an alternative to our peeling on the hub-weighted projection | yes (`feng2024unified`) |
| K22 | Identifying Adversarial Attacks in Crowdsourcing via Dense Subgraph Detection | A. Karaaslanli, P. A. Traganitis, A. Konar | 2025, ICASSP | Weighted bipartite worker–item graph + sequential peeling | Real crowdsourcing datasets | AUROC, AUPRC | Peel the **bipartite** user–attribute graph directly (no projection), finding members and the attributes they abuse together | yes (`karaaslanli2025crowd`) |
| K23 | Accelerating k-Core Decomposition by a GPU | A. Ahmad, L. Yuan, D. Yan, G. Guo, J. Chen, C. Zhang | 2023, ICDE | Optimised GPU peeling | Large graphs | Time, memory | k-core as a fast pre-filter on large projections (CPU is enough at our scale **[judgement]**) | yes (`ahmad2023gpukcore`) |
| K24 | The K-Core Decomposition Algorithm Under the Framework of GraphBLAS | L. Li, H. Chen, P. Li, J. Han, G. Wang, G. Zhang | 2021, HPEC | Algebraic k-core in GraphBLAS | Large sparse graphs | Runtime | Same as K23 | yes (`li2021graphblas`) |
| K25 | Systematic Cross-System Optimization of Parallel Hypergraph K-Core Decomposition | Y. Jiang | 2026, ECNCT | Benchmark of HK vs HyperCD variants | 7 real hypergraphs | Runtime, speedup, scalability | Hypergraph view: a shared attribute is a hyperedge over its users; hypergraph k-core avoids the clique blow-up of the projection | **no** |
| K26 | Differential Privacy from Locally Adjustable Graph Algorithms: k-Core, Low Out-Degree Ordering, Densest Subgraphs | L. Dhulipala, Q. C. Liu, S. Raskhodnikova, J. Shi, J. Shun, S. Yu | 2022, FOCS | DP algorithms for k-core and densest subgraph | theory | approximation bounds | DP release of aggregate ring/density statistics on a shared dashboard | yes (`dhulipala2022dp`) |
| K27 | A differentially private non-overlapping community detection method based on improved Louvain (DPI-Louvain) | X. Li, S. Dong, S. Li | 2023, DSIT | Exponential mechanism in Louvain + Laplace noise on inter-community edges | Two real social networks | Modularity and accuracy under privacy | Same as K26, community side | yes (`li2023dplouvain`) |
| K28 | Research on an Incremental Community Detection Algorithm for Large-Scale Dynamic Complex Network | B. Zhang, H. Liu, Y. Zhang | 2026, ICBDSE | Supernode compression of past communities, local update per block | Synthetic networks of varying size and degree | Modularity, runtime, memory vs Full-Louvain / Block-Louvain | Incremental Louvain baseline (our Louvain baseline is full-graph on a timer) | yes (`zhang2026incremental`) |
| K29 | Incremental Community Detection in Distributed Dynamic Graph | T. Abughofa, A. A. Harby, H. Isah, F. Zulkernine | 2021, BigDataService | Incremental community maintenance on distributed dynamic graphs | not recorded (text layer is garbled) | not recorded | Same as K28 | yes (`abughofa2021incremental`) |
| K30 | Improving Louvain Algorithm by Leveraging Cliques for Community Detection | (CSASE 2020 proceedings; authors not extracted) | 2020, CSASE | Seed Louvain with cliques | Synthetic and real | Runtime, partition quality | Low; seeding communities with detected cliques | **no** |
| K31 | Jaccard Based Similarity Index in Graphs: A Multi-Hop Approach | S. Varma, S. Shivam, A. Thumu, A. Bhushanam, D. Sarkar | 2022, DELCON | Shortest-path-based Jaccard-style similarity | not recorded | link prediction quality | Multi-hop overlap for mixed-attribute rings whose members share nothing directly | yes (`varma2022jaccard`) |
| K32 | Enhancing Localization Precision in Range-Free WSNs via Adamic–Adar Hop Conversion and ELM | M. Islam, C. Guo | 2026, RFAT | Adamic–Adar similarity as fractional hop count | Simulation | Localisation error | Low; one more use of Adamic–Adar (our hub weight is in that family) | **no** |
| K33 | Using K-core Decomposition on Class Dependency Networks to Improve Bug Prediction | Y. Qu et al. | 2021, IEEE TSE 47(2) | Coreness as a ranking signal | 18 open-source Java systems | Effort-aware ranking metrics | Coreness of a ring's members as a ranking feature | **no** |
| K34 | Enhancing Traffic Prediction with Interpretable Community Embeddings via Louvain | B. Durys, I. Pineda | 2023, TechDev | Louvain communities as learnable embeddings in TGCN | Urban road network | Prediction error | Low; community id as a feature | **no** |
| K35 | Study on Regional Traffic Sub-Area Division Based on Improved Louvain and Correlation Degree | (CAC 2022; authors not extracted) | 2022, China Automation Congress | Improved Louvain with domain correlation weights | One real road network | Modularity | Low; domain-weighted Louvain (analogous to running Louvain on our hub-weighted graph) | **no** |

### Kept, explainability and calibration

| # | Title | Authors | Year, venue | Core method | Datasets | Metrics | Idea to borrow | In bib? |
|---|---|---|---|---|---|---|---|---|
| K36 | Evaluating Robustness of Counterfactual Explanations | A. Artelt et al. | 2021, IEEE SSCI | Formal + empirical robustness of closest vs plausible counterfactuals under input perturbation | Toy + three standard datasets | Counterfactual distance under perturbation | Stability metric for our counterfactuals: perturb ring features, compare counterfactual targets | yes (`artelt2021robustness`) |
| K37 | Consistent Counterfactual Explanations via Anomaly Control and Data Coherence (ACDC) | M. Movin, F. Siciliano, R. Ferreira, F. Silvestri, G. Tolomei | 2025, IEEE TAI 6(4) | One-class-guided counterfactual search; consistency under model retraining | Tabular benchmarks | Validity, consistency across model updates, plausibility | Consistency check: do our counterfactuals still hold after retraining on other seeds / after feedback moves thresholds? | yes (`movin2025acdc`) |
| K38 | Calculating and Visualizing Feature Importance Values for Counterfactual Explanations (CFI) | B. Meulemeester, R. M. B. de Oliveira, Y. He, D. Martens | 2026, IEEE Access 14 | Per-feature importance of a counterfactual change + visualisations | Tabular benchmarks | importance and user-facing visual design | UI: show how much each changed feature moves the score in the alert drawer and report | yes (`meulemeester2026cfi`) |
| K39 | ACTS: Adaptive Counterfactual Explanations for Time Series Data Using Barycenters | P. Hosseinzadeh, P. Li, O. Bahri, S. F. Boubrahimi, S. M. Hamdi | 2024, IEEE BigData | DBA/DTW-based sparse, contiguous counterfactuals | Real time-series datasets | sparsity, contiguity, validity | Sparsity/plausibility as counterfactual quality metrics | **no** |
| K40 | Physics-Guided Counterfactual Explanations for Large-Scale Multivariate Time Series (SEP) | P. Patil, A. Ji, B. Aydin | 2025, IEEE BigData | Domain-constrained counterfactuals | GOES proton-flux time series | validity/plausibility | Domain constraints on counterfactuals (e.g. a hub cannot shrink below its benign users) | **no** |
| K41 | CREDENCE: Counterfactual Explanations for Document Ranking | J. Rorseth, P. Godfrey, L. Golab, M. Kargar, D. Srivastava, J. Szlichta | 2023, ICDE (demo) | Interactive counterfactuals for rankers; users build their own perturbations | IR | demo | **Interactive "what-if" panel** for the alert queue (an alert ranking is a ranking) | **no** |
| K42 | Segmentation-Based Image Manipulation for Interactive Counterfactual Explanations in Medical Image Analysis | H. Montenegro, J. S. Cardoso | 2026, ISBI | Interactive manipulation of a clinical factor | Chest radiographs | correlation of factor and prediction | Low; reinforces interactive what-if UI | **no** |
| K43 | Explaining SAR ATR Models Predictions with Counterfactual Explanations | H. Remusati et al. | 2024, IEEE Radar Conf. | Counterfactuals aggregated into semi-global explanations | MSTAR | qualitative | Semi-global explanations: aggregate counterfactuals per ring type for the experiments page | **no** |
| K44 | Unveiling Deepfakes with Latent Diffusion Counterfactual Explanations | C. Yang, B. Peng, J. Dong, X. Zhang | 2025, ICASSP | Diffusion-generated counterfactuals | Deepfake datasets | quality/efficiency | Low | **no** |
| K45 | From Black-Box to Transparent AI in Agriculture: Grad-CAM + Counterfactuals | M. S. Sarkar | 2025, EICT | Grad-CAM + counterfactuals | Rice leaf images | accuracy | Low | **no** |
| K46 | Integrating Explainability and Fairness in Credit Risk Prediction (TabNet, LightGBM, SHAP, counterfactuals) | S. Kapoor, S. Jain, Vidushi | 2026, ICCSC | Hybrid model + SHAP + counterfactuals + fairness checks | FICO | accuracy-type and fairness metrics | Fairness check: false-alert rate by benign hub category (office vs carrier NAT vs family) | **no** |
| K47 | Local Temperature Scaling for Probability Calibration | Z. Ding, X. Han, P. Liu, M. Niethammer | 2021, ICCV | Learned per-location temperature | Segmentation datasets | ECE and related | Calibration beyond global Platt (e.g. per ring type) | yes (`ding2021temperature`) |
| K48 | Impact of Platt Scaling on Calibration in ML-Based Wireless Resource Allocation | R. Raina, N. Simmons, D. E. Simmons, M. D. Yacoub, S. L. Cotton | 2025, ICMLCN | Platt scaling, reliability plots with log binning | Simulated Rayleigh channels | NLL, reliability diagrams | Log-binned reliability plot for rare high-risk alerts | **no** |
| K49 | Improved Probability Calibration Techniques for Accurate Heart Disease Risk Assessment | A. Akilandeswari | 2025, ICSCSS | Isotonic vs raw LR | Heart disease dataset | Brier, reliability diagrams | Isotonic as the comparison to our current calibrator | **no** |
| K50 | Calibrated and Explainable Prediction of Strong-Positive ANA Results (SHAP + calibration) | K. Gencer, M. Gürbüz, G. Gencer | 2026, IEEE Access | Gradient boosting + calibration + SHAP; patient-level splits | 12,674 ANA test records (2020–2022) | discrimination + calibration | Group-level splitting (ours: seed-level, ring-level) to avoid leakage | **no** |

### Kept, low relevance (gradient boosting in unrelated domains; abstract-level read)

| # | Title | Year, venue | Note |
|---|---|---|---|
| K51 | Revolutionizing Credit Risk: Gradient-Boosting Techniques (R. bin Tareaf, M. Abujarour, F. Zinn) | 2024, ICOIN | XGBoost/LightGBM/CatBoost on 2.3M AmEx records; supports GB as comparison scorer only |
| K52 | Earthquake Prediction Model Using RF and GB (D. B. Babu et al.) | 2024, ICCES | out of domain |
| K53 | Employee Attrition Using Gradient Boosting (T. K. Rohan, T. Padmakara, G. Abirami) | 2025, ICOEI | out of domain |
| K54 | Enhancing Malaria Incidence Prediction (D. Nsanzabandi, P. Nizeyimana) | 2024, SmartBlock4Africa | out of domain |
| K55 | Extreme Gradient Boosting Classification of Motor Imagery (M. Vijay et al.) | 2020, INDICON | out of domain |
| K56 | Greenland Daily NDSI Reconstruction (F. Ye, Q. Cheng, W. Hao, D. Yu) | 2023, IGARSS | out of domain |

**Recommendation [judgement]:** cite K1–K13, K16, K17, K20–K29, K31, K36–K38,
K41, K47 at most. Citing K51–K56 or the image-domain counterfactual papers
would weaken the paper with reviewers.

---

## (b) Gap analysis against the 2020+ papers

| Paper(s) | What they do | What we lack (fact) or could add |
|---|---|---|
| K3, K4, K5, K6, K7, K8 (graph-fraud GNNs) | Learn node scores on heterogeneous, heterophilous graphs; evaluate on YelpChi/Amazon/T-Finance/Elliptic with AUC, F1-macro, G-Mean | No learned graph baseline at all (Threats to Validity). No node-level AUC reported for our method, so no common metric with this literature |
| K11, K12 | Show tabular boosted ensembles match or beat GNNs under **temporal** splits; performance collapses after drift | No tabular node/ring classifier baseline (e.g. XGBoost on the same 19 features without the rule stage). Drift scenario exists but no time-sliced (prequential) reporting |
| K1 (GB-FRD), K2 (behavioural soft links) | Ring/graph fraud on payment graphs; K2 explicitly identifies over-linkage through shared IPs | We do not use embeddings (Node2Vec/FastRP) as features; no soft-link edge type; no comparison with an over-concentration filter (K2's HDBSCAN pruning is a learned cousin of the degree cap) |
| K3, K4, K6 (camouflage, heterophily) | Explicitly model fraudsters connecting to benign nodes | decoy_edges exists but its strength is not swept; E6 sweeps only rate, ring size and window |
| K8, K3 (label noise) | Robustness to wrong training labels | Scorer trained on clean simulator labels only; feedback loop untested under noisy analysts |
| K16, K47–K50 (calibration) | Brier, reliability, Precision@k, Lift@k, isotonic vs Platt, group-level splits | Calibration only at snapshot level (`docs/scoring.md`); no ring-level reliability in the paper; no Lift@k; one calibrator |
| K36–K38, K9 (explanations) | Measure counterfactual robustness, consistency across retraining, feature importance of the change | Counterfactuals are produced but never evaluated; spec RQ4 (explanation quality) unanswered |
| K41, K38 (interactive explanation UIs) | Interactive what-if and visual importance | Drawer shows static counterfactual sentences only (`web/src/components/RingDetailDrawer.tsx`) |
| K20 (HYADES) | Measures Redis Streams consumer lag/throughput vs batch size and block timeout | Redis Streams path exists but is not in any experiment; latency only in-memory |
| K21, K22, K25 (dense subgraph, bipartite peeling, hypergraph cores) | Densest-subgraph and bipartite peeling with guarantees; hypergraph cores | We peel a projected user–user graph; no comparison with bipartite peeling or a densest-subgraph formulation |
| K28, K29 (incremental communities) | Incremental Louvain with measured runtime vs full | Our Louvain baseline is full-graph on a timer; an incremental community baseline would make RQ2 fairer |
| K26, K27 (differential privacy) | DP k-core / densest subgraph / Louvain | No privacy mechanism; "advanced addition" 3 (salted identifiers) not implemented |
| K16 (AMLworld with rolling features) | Uses rolling 1/7/30-day behavioural features on IBM AML | Our AMLworld replay is a 4-day slice with a 1 h window (`numbers.tex` `\PubAmlWindow`=1), 0/55 groups |

---

## (c) Ranked novel additions

Ranking is by (credibility gain × feasibility) **[judgement]**. Effort: S ≈ ≤2
days, M ≈ 3–6 days, L ≈ >1 week, for one developer **[assumption]**. "How to
evaluate" never presupposes an outcome; every reported figure must come from a
new logged run with run_id, config hash and seed, as in M1–M8.

### A1. End-to-end latency on the real stack (Neo4j + Redis Streams) — credibility, S/M
- **What:** run E4 and a shortened E1 with `--backend neo4j` and the Redis
  Streams bus; record ingest→graph-write, per-batch detect, event→flag
  p50/p95/p99, consumer lag, events/s. Sweep consumer `count` (batch) and
  `block` timeout as K20 does.
- **Why:** removes the explicit Threats-to-Validity caveat "Latency … in-memory
  … Neo4j adds query and transport cost that we did not include".
- **Motivated by:** K20 (HYADES); C2 claim in `master_prompt.md`.
- **Evaluate:** new `results/e8_stack_latency/results.csv`; compare against
  in-memory runs of the same seeds with a paired test; check identical flagged
  rings (stream digest equality, as the no-incremental ablation does).
- **Risks:** laptop memory (7.7 GB noted); Neo4j JVM warm-up must be excluded
  and reported; Docker timing noise → report per-seed spread.

### A2. Explanation-quality evaluation (answers the spec's RQ4) — credibility, M
- **What:** four measurable properties of every alert's explanation:
  1. *Counterfactual validity* — apply the counterfactual change to the feature
     vector, re-score, check it crosses the threshold.
  2. *Stability* (K36) — perturb non-actionable features by small noise, measure
     change in counterfactual targets.
  3. *Consistency* (K37) — retrain the scorer on a disjoint training-seed set;
     fraction of counterfactuals still valid.
  4. *Evidence fidelity* (Oracle-only) — fraction of evidence-subgraph users
     that are true ring members, and fraction of true members covered.
  Plus CFI-style per-feature importance of each counterfactual (K38).
- **Why:** turns C3 from a feature into a measured claim; IN-GFD (K9) and the
  counterfactual papers evaluate this, we do not.
- **Evaluate:** `results/e9_explanations/results.csv` over E1 test seeds; report
  distributions, not cherry-picked examples.
- **Risks:** validity is trivially high for LR counterfactuals computed in
  closed form → report it honestly as a sanity check and put weight on
  stability/consistency/fidelity.

### A3. Ring-level calibration and operational metrics — credibility, S
- **What:** reliability diagram and Brier/ECE at **ring alert level** (not
  snapshot), Precision@k and Lift@k for k in {1%, 5%, 10%} of alerts, isotonic
  vs Platt (and per-ring-type temperature as a stretch, K47).
- **Why:** `docs/scoring.md` itself flags overconfidence in middle buckets; K16
  shows these are the metrics AML practitioners expect.
- **Motivated by:** K16, K47, K48, K49, K50.
- **Evaluate:** reuse E1 runs (detections.jsonl carry scores) → new table; no
  new simulation needed except for the calibrator comparison.
- **Risks:** few ring-level positives per seed → wide CIs; pool across seeds and
  state counts.

### A4. Learned baselines: tabular ensemble and one GNN — credibility, M/L
- **What:** (i) XGBoost/GB on the same 19 ring features over **all** candidate
  groups (no rule stage) and (ii) GraphSAGE (PyTorch Geometric) node classifier
  on the heterogeneous user–attribute graph, with node scores turned into rings
  by a fixed, documented grouping (e.g. connected components of top-scored
  users in the hub-weighted projection). Temporal train/test split by seed and
  time as in K11/K12. Optional (iii) FastRP/Node2Vec embeddings as extra ring
  features (spec "advanced addition" 1; K1).
- **Why:** answers the "no GNN baseline" threat directly; K11/K12 make the
  expected comparison class (tabular vs GNN) standard.
- **Evaluate:** same ring-level metrics, same streams (stream digest), paired
  Wilcoxon vs proposed; also report node-level AUC for every method so the
  numbers can sit next to the GFD literature (labelled as not comparable to
  their datasets).
- **Risks:** grouping step is a design choice that can favour or penalise the
  GNN → fix it before seeing test results and report the alternative in an
  appendix; dependency weight (torch) → optional extra `[gnn]`.

### A5. Camouflage-strength and evasion-strength sweeps — credibility, S/M
- **What:** sweep decoy edges per member, hub size for hub_hiding (already E5),
  low-and-slow rate multiplier, identity-rotation period. Uses existing
  simulator knobs; add any missing knob as a config field.
- **Why:** K3/K4/K6 centre on camouflage/heterophily; our E6 has no evasion
  strength axis although the spec lists "evasion strength" as a sweep.
- **Evaluate:** recall-by-evasion curves with 95% CI over seeds; proposed vs
  cap 10 vs Louvain.
- **Risks:** the curves may confirm "every method fails" for rotation/slow
  rings; that is still a result and should be reported as such.

### A6. Early-warning lead time — credibility, S
- **What:** report the existing `early_warnings_before_activation` column plus
  lead-time distribution (activation − first early warning) and the precision
  of early warnings.
- **Why:** spec M4 asks for it; data already logged; currently unreported.
- **Evaluate:** derived from E1 run logs; no new runs.
- **Risks:** small counts; report as counts with seeds.

### A7. Analyst-feedback loop under label noise — credibility + appeal, M
- **What:** simulated analyst with review budget b alerts/hour and error rate
  ε (confirm/dismiss using ground truth, flipped with probability ε) driving
  `AlertPolicy`; measure precision/recall over time vs no feedback; repeat for
  ε in a small grid. The same loop powers the web app's feedback buttons.
- **Why:** feature exists but is untested; K8 and K3 make label-noise
  robustness a standard question.
- **Evaluate:** `results/e10_feedback/`; rolling-window metrics already exist
  in `src/fraudsim/metrics/`.
- **Risks:** the adaptive attacker and feedback interact → run with attacker
  feedback on and off.

### A8. Drift: prequential evaluation and hub-weight refit — credibility, M
- **What:** time-sliced (prequential) metrics on `drift.yaml` and a longer drift
  run; a simple drift detector on the benign hub-size distribution that refits
  the hub weight (spec "advanced addition" 2). Also lets time decay and
  hysteresis be tested on long streams (limitation 8).
- **Motivated by:** K11 (performance collapse after a market shutdown), K12.
- **Evaluate:** per-slice F1 with and without refit, same seeds.
- **Risks:** our drift is synthetic; claims stay about the simulator.

### A9. Bipartite / densest-subgraph ring extraction variant — credibility, M
- **What:** an alternative candidate extractor that peels the weighted
  user–attribute bipartite graph (K22) or solves weighted densest subgraph (K21)
  instead of peeling the projection; run as a new ablation arm.
- **Why:** connects C1 to established dense-subgraph theory; reviewers familiar
  with K21/K22 will ask why projection.
- **Evaluate:** E1/E3 with the variant; runtime per batch.
- **Risks:** may lose on precision; that is fine, it is an ablation.

### A10. Incremental community baseline — credibility, M
- **What:** incremental Louvain (supernode compression as in K28) as a
  streaming baseline, replacing/adding to the timer-based GDS Louvain.
- **Why:** makes RQ2 fairer (incremental vs incremental).
- **Evaluate:** E1 accuracy + E4 latency.
- **Risks:** implementation effort; GDS has no incremental Louvain → Python
  implementation on the in-memory store only **[assumption]**.

### A11. AMLworld extended replay — credibility, M
- **What:** longer slice (up to the full 18 days if memory allows), windows of
  24 h / 7 d, AMLworld pattern-type breakdown (cycle, fan-in, gather-scatter …
  listed in `docs/datasets.md`), rolling behavioural features (K16).
- **Why:** the only public set with group labels; current window is 1 h.
- **Evaluate:** group recall by pattern type, account precision; state that it
  cannot test hub weighting.
- **Risks:** may stay near zero; still more honest and informative than one
  slice.

### A12. Privacy: pseudonymised identifiers, DP aggregates as stretch — appeal + credibility, S (hash) / L (DP)
- **What:** salted keyed hashing (HMAC) of device/card/IP ids at ingest, with a
  test that detections are byte-identical (spec "advanced addition" 3); stretch:
  DP noise on dashboard aggregate counts (K26/K27).
- **Evaluate:** determinism test (stream digest + detections equality).
- **Risks:** DP utility loss on tiny counts; keep DP to aggregate KPIs only.

### Product-appeal additions (for the web app, not research claims)
- Interactive what-if panel on alerts (K41, K38): move a feature slider, re-score
  via the existing scorer, show which counterfactual flips the decision.
- Semi-global explanations per ring type on the Experiments page (K43).
- Fairness view: false-alert rate per benign hub category (K46).
- Investigation report / SAR-style summary with evidence subgraph and
  explanation (no paper; product need).

---

## (d) Recommended Phase 2 scope

**Must-have (research):** A1, A2, A3, A6, A4 (tabular ensemble at minimum; GNN
if time), A5.
**Must-have (product):** the web app milestones in `phase2_prompt.md` (dashboard,
simulator, alerts/case management with feedback, explorer, reports, experiments,
configuration, auth, CI, deployment).
**Stretch:** A7, A8, A9, A10, A11, A12 (hash part is cheap and can be pulled
into must-have), GNN half of A4, embeddings as features.

Ordering rationale **[judgement]:** A1/A3/A6 reuse existing logs or code paths
and close stated threats quickly; A2 answers an RQ the spec promised; A4/A5 are
the comparisons reviewers of the K3–K12 literature will ask for first.

Out of scope: claims about real-world performance; anything that needs data with
shared-attribute links (none found in public form, `docs/datasets.md`).
