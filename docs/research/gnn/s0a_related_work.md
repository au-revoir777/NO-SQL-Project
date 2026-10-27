# Stage 0A — Related-work search and novelty audit for EvidGNN

Date of search: 2026-10-27. Tools: WebSearch (standard, plus extended for niche/recent items) and WebFetch on URLs that appeared in search results. No compute was run.

Status key: **VERIFIED** = I opened the paper's own page or PDF (or the publisher/proceedings record) and found the same record in a second source (arXiv listing, proceedings, DBLP-like index, publisher, or institutional listing). **UNVERIFIED** = anything less. For arXiv-only items, "VERIFIED (arXiv)" means the arXiv record was confirmed, not a peer-reviewed venue.

---

## 1. Summary

- **Component 2 (exact incremental GNN inference) is mostly already done.** InkStream, RIPPLE (ICDCS 2025), NrtInc (arXiv 2026), StreamTGN (arXiv 2026), STAG and Spade (for peeling, not GNNs) already recompute only the affected region and claim, or prove, equality with full recomputation. Reposition it as a correctness property of EvidGNN, not as a contribution.
- **Component 1 is partly done.** Edge-feature gates and attention biases exist (FraudGT, ICAIF 2024; RGH-GNN, arXiv Oct 2026). Top-k neighbours by an importance score exist (PinSage). Learned camouflage filters exist (CARE-GNN, PC-GNN, GraphConsis). Conjunctive edge construction exists (PromoGuardian, IEEE S&P 2026). I found no GNN that routes messages through a busy shared-attribute node only when the pair has corroborating evidence, with label-free hub discounting. That narrow gap is open.
- **Component 3 and the ring scorer are partly done.** Weak labels, pseudo-labels and few-label GNNs are common (DeFraudNet, L2IR, BSL, ConsisGAD, SpaceGNN). Group-level GNN detectors exist (GFDN, UniGAD, Gr-GAD). Training on a streaming rule pipeline's confirmed rings, measured across label budgets, was not found. Faithfulness "by construction" is contested (Azzolin et al., ICLR 2025).
- **Correction for the paper.** FRAUDAR's recommended column weight is 1/log(x+c) with c=5 in its experiments (TKDD version). It is not 1/ln(1+d). Say "a FRAUDAR-style column weight with c=1", or cite the exact form.

---

## 2. Related-work matrix (papers read in depth)

Abbreviations: SA = shared-attribute relation; hub = high-degree node or group; MP = message passing; NS = neighbour selection; inc = incremental/streaming; WS = weak supervision; expl = explanations. "n/s" = not stated in what I read.

| # | Paper | Q1 task/unit, labels | Q2 graph; SA hubs? | Q3 hub handling | Q4 NS rule, fan-out | Q5 edge evidence gates MP? | Q6 inc; exactness | Q7 labels/WS | Q8 expl & faithfulness | Q9 data/metrics | Q10 code | Status | URL |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PromoGuardian (Li et al., IEEE S&P 2026) | Users in promotion-abuse groups; 3-class (fraud/normal/unlabelled) | User–user edge only if same product same day **and** share a value in one of 8 relations (geohash, store, coupon…). Yes, SA. | n/s; the largest relation (retail store) gets no mitigation | n/s (no graph sampling described) | Yes: concatenated TransR relation embeddings scaled by co-occurrence weights form edge features | Daily offline batch over 7 days; no exactness | Semi-supervised autoencoder; top 1.2% become seeds; propagation within groups (threshold 0.65) | None; rule-based risk grading in production | PPA (~5.69M users, ~29M edges); P/R/F1; production precision 0.93 | github.com/0xllssFF/PromoGuardian | VERIFIED | https://arxiv.org/pdf/2510.12652 |
| 2 | Spade (Jiang et al., PVLDB 16(3), 2022) | Dense fraudulent communities; labels only for evaluation | Users and stores; transaction edges; no SA relations | FD edge weight 1/log(x+c) on the object vertex degree | Not applicable (peeling) | Edge weights scale density; no MP | Yes. Incremental peeling, proved equal to static peeling on G⊕ΔG; benign edges batched, urgent edges immediate | Not applicable | Case studies only | Grab1–4 (4–6M vertices), Amazon, Wiki-Vote, Epinion; latency, prevention ratio | No code linked in paper | VERIFIED | https://arxiv.org/pdf/2211.06977 |
| 3 | CARE-GNN (Dou et al., CIKM 2020) | Node (review/user); spam or helpful-vote labels | Multi-relation; R-U-R, R-S-R, R-T-R (Yelp), U-P-U, U-S-U, U-V-U (Amazon). Yes, SA. | No dedicated mechanism; top-p caps neighbours proportionally | Top-p by label-aware similarity (1−L1 of MLP predictions); p learned by RL/bandit per relation | Learned thresholds weight relations; no pair-evidence gate | No | Supervised, balanced mini-batches | None (relation weights analysed) | YelpChi, Amazon; AUC, Recall | github.com/YingtongDou/CARE-GNN | VERIFIED | https://arxiv.org/pdf/2008.08692 |
| 4 | InkStream (Wu, Li, Mitra; arXiv 2309.11071; a later NUS-hosted version is filed "IPDPS25") | Generic node embeddings; no fraud | Cora, PubMed, Reddit, Yelp | n/s | None by default. Sampling possible if previous samples are cached and diffs applied as edge updates | No | Yes. Event-based updates in the k-hop affected area with pruning. Claims bit-identical output for min/max and arithmetic equivalence for mean/sum. Analytical argument only; no equivalence test | Not applicable | Not applicable | Speedup 2.5–427× (CPU) over affected-area recompute | github.com/WuDan0399/InkStream | VERIFIED (arXiv); venue UNVERIFIED | https://arxiv.org/pdf/2309.11071 |
| 5 | RIPPLE (Naman & Simmhan, ICDCS 2025) | Generic | Arxiv, Reddit, Products, Papers | n/s | Full neighbourhood (argues sampling is non-deterministic) | Weighted-sum aggregator supported | Yes. Delta propagation. Claims exact embeddings "within the limits of floating-point precision"; no numeric equality test reported | Not applicable | Not applicable | Throughput and latency; batch sizes 1–1000 | n/s | VERIFIED (arXiv; venue stated in preprint) | https://arxiv.org/html/2505.12112v1 |
| 6 | NrtInc — Incremental GNN Embedding Computation on Streaming Graphs (Wang et al., arXiv 2603.20622, 2026) | Generic | ogbn-arxiv/products/papers, Reddit, Twitter, Friendster | n/s | Full neighbour; sampling treated as a baseline | Attention models handled as "constrained" | Yes. Recomputes affected edges layer by layer. Theorem 1 gives algebraic conditions. Tested: final-layer MSE below 1e-4 against full recompute | Not applicable | Not applicable | 1.7–145.8× speedup | none | VERIFIED (arXiv) | https://arxiv.org/html/2603.20622v1 |
| 7 | StreamTGN (Zhang et al., arXiv 2603.21090, 2026) | TGN/TGAT serving | 8 temporal graphs | n/s | Temporal neighbours | n/s | Yes. Marks nodes within L hops of new edges as dirty and recomputes only those. Exact for most stages; delta mode and relaxed batching have bounded error (AP drop under 1% up to B=1000) | Not applicable | Not applicable | 4.5–739× (TGN) | n/s | VERIFIED (arXiv) | https://arxiv.org/html/2603.21090 |
| 8 | FraudGT (Lin et al., ICAIF 2024) | Edge (transaction) classification; illicit labels | Account nodes, transaction edges (directed multigraph); no SA | n/s | Subgraph around target transactions; attention over direct neighbours | **Yes.** Sigmoid edge gate G_ij=σ(E'_ij W_G) on messages, and edge-attribute attention bias b_ij added before softmax | No; batch throughput only | Fully supervised | None | AMLworld Small/Medium/Large HI/LI; temporal splits; F1 | github.com/junhongmit/FraudGT | VERIFIED | https://jshun.csail.mit.edu/FraudGT.pdf |
| 9 | BRIGHT (Lu et al., CIKM 2022) | Transaction; chargeback labels | Transaction–entity graph (address, email, IP, device, phone, payment token, account). Yes, SA. | n/s; Louvain cuts components larger than 32k for training | No sampling at inference (1-hop entities) | No | Lambda design. Entity embeddings batch-refreshed daily; RT net is 1 conv layer. Claimed equivalent to end-to-end; staleness acknowledged | Supervised | Defers to xFraud | ~7M eBay txns; AUC, AP; P99 latency | n/s | VERIFIED | https://arxiv.org/pdf/2205.13084 |
| 10 | xFraud (Rao et al., PVLDB 15(3), 2022) | Transaction | txn–payment token–email–address–buyer. Yes, SA. | Not handled; graphs are sparse (~2 edges/node) | GraphSAGE-style k-hop sampling in detector+ | No | Incremental training mentioned (appendix) | Supervised | GNNExplainer + edge centrality hybrid; scored by **top-k hit rate vs human annotations**, not faithfulness | eBay small/large/xlarge (up to 1.1B nodes); AUC | github.com/eBay/xFraud | VERIFIED | https://arxiv.org/pdf/2011.12193v2 |
| 11 | GEM (Liu et al., CIKM 2018) | Account (Alipay malicious) | Account–device bipartite, 6 device types. Yes, SA hubs. | Sum aggregation, so hubs contribute **more**; not analysed | Full T-hop (T=5) | Attention per device type only | Daily rebuild; real-time listed as future work | Supervised (delayed ground truth) | Device-type attention weights | ~8M vertices; F1, AUC | n/s | VERIFIED | https://arxiv.org/pdf/2002.12307 |
| 12 | GraphConsis (Liu et al., SIGIR 2020) | Review spam | R-U-R, R-S-R, R-T-R. Yes, SA. | **Removes products with more than 800 reviews** (preprocessing) | Consistency score threshold, then sampling ∝ score; fan-out 10/5 | Relation attention | No | Supervised | None | YelpChi; F1, AUC | DGFraud toolbox | VERIFIED | https://ar5iv.labs.arxiv.org/html/2005.00625 |
| 13 | GAGA (Wang et al., arXiv 2302.10407; ACM 2023 template; venue believed WWW 2023) | Node; partial labels | Multi-relation YelpChi/Amazon (SA), BF10M | n/s | Full K-hop, neighbours grouped by label (fraud/benign/unknown) | No; attention over groups | Inductive only | Training labels used as input features | Attention visualisation | YelpChi, Amazon, BF10M; 40/10/50; AUC, AP, F1-macro | github.com/Orion-wyc/GAGA | VERIFIED (arXiv); venue UNVERIFIED | https://arxiv.org/pdf/2302.10407 |
| 14 | PinSage (Ying et al., KDD 2018) | Recommendation | Pin–board | Random-walk importance replaces raw degree | **Top-T neighbours by normalised random-walk visit counts** (T=50); importance pooling | Visit-count-weighted mean | MapReduce inference avoids repeated computation; not streaming | Not applicable | Not applicable | Pinterest 3B items | n/s | VERIFIED | https://ai.stanford.edu/~jure/pubs/pinsage-kdd18.pdf |
| 15 | SEFraud (Li et al., KDD 2024 per paper) | Node; Yelp/Amazon/ICBC | Heterogeneous (HGT) | n/s | All neighbours | Learned edge and feature masks reweight the graph fed to the detector | No | Supervised | Self-explainable masks; specific faithfulness metrics truncated in my read | AUC, Recall; ICBC deployment | n/s | VERIFIED (arXiv); venue per paper | https://arxiv.org/html/2406.11389v1 |
| 16 | TravelFraudBench (Sajja, arXiv 2604.21093, 2026) | Node plus **ring recovery** (ring found if ≥80% of members score >0.5) | 9 node types including device, IP, card; projected user–user co-occurrence graph | n/s | GraphSAGE mean (fan-out n/s) | No | No | Exact synthetic labels; ring-wise split | None | 3 ring types; GraphSAGE best (AUC 0.992, 100% ring recovery) | MIT licence; github.com/bhavana3/travel-fraud-graphs | VERIFIED (arXiv) | https://arxiv.org/pdf/2604.21093 |
| 17 | Large-scale graph clustering with heterogeneous link transformation (Liu, arXiv 2512.19061) | Clusters as candidate rings; unsupervised | Hard links (phone, email, card, ID, bank) merged by union-find. Soft links (device, cookie, IP) become weighted super-node edges. Yes, SA. | None; coincidental sharing acknowledged as noise | Not applicable (LINE + HDBSCAN) | Summed, time-decayed soft-link weights | 4-hour micro-batches; online union-find; weekly full rerun; no exactness | None | None | 25M accounts; coverage, precision, purity | none | UNVERIFIED (single source) | https://arxiv.org/html/2512.19061v1 |
| 18 | L2IR (Guo et al., arXiv 2605.26040) | Node; review fraud | Amazon/Yelp relations (SA) | Not addressed | LLM audits top-4000 "contradictory" edges | Edge reports pooled into node features | No | **Self-training pseudo-labels** with asymmetric thresholds; capped rounds | n/s | Amazon, Yelp; AUPRC | n/s | UNVERIFIED (single source) | https://arxiv.org/pdf/2605.26040 |
| 19 | DeFraudNet (Mathew et al., ECML-PKDD 2021) | Transaction (food delivery) | Customer–customer graph, GCN embeddings | n/s | n/s | n/s | Real-time serving claimed | **Snorkel labelling functions** from rules, CS logs and heuristics; autoencoder denoising | n/s | Recall at fixed precision | n/s | UNVERIFIED (only mlanthology record opened) | https://mlanthology.org/ecmlpkdd/2021/mathew2021ecmlpkdd-defraudnet |
| 20 | Rule-anchored graph learning for synthetic identity fraud (Nguyen & Chiu, Discover Informatics 1:22, 2026) | Client | Client–SSN–Email–Phone heterogeneous graph; SA hubs | None; rule score rises with hub sharing | n/s | No; score-level fusion (α=0.05 model, 0.95 rule) | No | Fully labelled; rule kept as the backbone | Transparent rule score | PaySim-derived 2,433 profiles; PR-AUC, P@100 | n/s | UNVERIFIED (single source) | https://link.springer.com/article/10.1007/s44564-026-00024-z |
| 21 | GFDN (Yu et al., KDD 2023) | Group fraud; edge (click) and vertex (sockpuppet) | Customer–product bipartite | (α,β)-core features | GraphSAGE backbone | No | No | Semi-supervised, expert labels | n/s | Taobao, Tianchi, Bitcoin Alpha/OTC | github.com/yujianke100/GFDN | VERIFIED | https://cgi.cse.unsw.edu.au/~zhangw/files/2023_KDD_paper.pdf |
| 22 | Reconsidering Faithfulness in Regular, Self-Explainable and Domain-Invariant GNNs (Azzolin et al., ICLR 2025) | Explanation evaluation | Not applicable | Not applicable | Not applicable | Not applicable | Not applicable | Not applicable | Shows SE-GNNs leak information from unselected parts. Needs hard scores, explanation readout and local aggregation | Benchmarks | n/s | VERIFIED | https://proceedings.iclr.cc/paper_files/paper/2025/file/7969d456aede0ce6b36fb47cc64c495c-Paper-Conference.pdf |
| 23 | FRAUDAR (Hooi et al., KDD 2016; TKDD 11(4) 2017 extension) | Dense block (fraud users × objects) | User–object bipartite | **Column weight h(x)=1/log(x+c), c=5**; camouflage-resistant (Thm 4.4) | Not applicable | Weights in the density metric | None (temporal listed as future work) | Unsupervised | Not applicable | Twitter etc. | n/s | VERIFIED | https://alexbeutel.com/papers/tkdd_fraud_detection_with_camo.pdf |

Also read in some depth but not tabulated above: RioGNN (TOIS), STAG, InstantGNN, APAN, Money-mule RBIH (arXiv 2610.21314), "How Faithful are Self-Explainable GNNs?", RGH-GNN (abstract-level only), and the fake reviewer groups paper (arXiv 2603.08332). Their key facts are in §3.

---

## 3. Screened list (69 candidates)

| # | Title (short) | Year | Venue / ID | One-line relevance | Status |
|---|---|---|---|---|---|
| 1 | CARE-GNN: Enhancing GNN-based Fraud Detectors against Camouflaged Fraudsters | 2020 | CIKM; arXiv 2008.08692 | Learned top-p neighbour filter over shared-attribute relations | VERIFIED |
| 2 | PC-GNN: Pick and Choose (Liu, Ao, Qin, Chi, Feng, Yang, He) | 2021 | WWW (DOI 10.1145/3442381.3449989 inferred) | Label-balanced and neighbourhood samplers for imbalance | UNVERIFIED (ACM page fetch failed; Paper Digest and hyper.ai agree) |
| 3 | BWGNN: Rethinking GNNs for Anomaly Detection | 2022 | ICML, PMLR 162 | Spectral band-pass filters; standard GAD baseline | VERIFIED |
| 4 | GADBench | 2023 | NeurIPS D&B; arXiv 2306.12251 | Tree ensembles with neighbour aggregation beat specialised GNNs; include as baseline | VERIFIED |
| 5 | GraphSAGE | 2017 | NeurIPS (NIPS 30); arXiv 1706.02216 | Uniform fixed fan-out sampling baseline; it beat the rule pipeline | VERIFIED |
| 6 | GNNExplainer | 2019 | NeurIPS; arXiv 1903.03894 | Post-hoc subgraph explanations | VERIFIED |
| 7 | FRAUDAR | 2016 | KDD; DOI 10.1145/2939672.2939747 | Source of the column weight 1/log(x+c) | VERIFIED |
| 8 | Graph-Based Fraud Detection in the Face of Camouflage | 2017 | TKDD 11(4) | FRAUDAR extension; c=5; camouflage-resistance theorem | VERIFIED |
| 9 | Spade (evolving graphs) | 2022 | PVLDB 16(3); arXiv 2211.06977 | Exact incremental peeling with degree-weighted edges | VERIFIED |
| 10 | Spade demo | 2024 | PVLDB 17(12) demo | GUI and user-defined suspiciousness; Grab | VERIFIED |
| 11 | AMLworld (Altman et al.) | 2023 | NeurIPS D&B; arXiv 2306.16424 | Synthetic AML benchmark with complete labels | VERIFIED |
| 12 | DGraph (Huang et al.) | 2022 | NeurIPS D&B; arXiv 2207.03579 | ~3M-node financial dynamic graph with background nodes | VERIFIED |
| 13 | Bank Account Fraud (Jesus et al.) | 2022 | NeurIPS D&B; arXiv 2211.13358 | Tabular, not a graph; useful as non-graph control | VERIFIED |
| 14 | GHRN (Gao et al.) | 2023 | WWW | Heterophily edge pruning via spectrum | UNVERIFIED (Paper Digest only) |
| 15 | H2-FDetector (Shi et al.) | 2022 | WWW; DOI 10.1145/3485447.3512195 | Separates homophilic and heterophilic connections | UNVERIFIED (OpenAlex record only) |
| 16 | GAGA | 2023 | arXiv 2302.10407 (venue believed WWW 2023) | Label-grouped aggregation | VERIFIED (arXiv) |
| 17 | InkStream | 2023 | arXiv 2309.11071 | Exact incremental GNN inference (min/max; mean/sum in later version) | VERIFIED (arXiv) |
| 18 | RIPPLE | 2025 | ICDCS (per preprint); arXiv 2505.12112 | Exact delta propagation for linear aggregators | VERIFIED (arXiv) |
| 19 | RIPPLE++ | 2026 | arXiv 2601.12347 | Generalised incremental programming model | VERIFIED (arXiv) |
| 20 | NrtInc: Incremental GNN Embedding Computation on Streaming Graphs | 2026 | arXiv 2603.20622 | Exactness theorem plus MSE test | VERIFIED (arXiv) |
| 21 | StreamTGN | 2026 | arXiv 2603.21090 | L-hop dirty set, batch serving, exactness analysis | VERIFIED (arXiv) |
| 22 | InstantGNN | 2022 | KDD; arXiv 2206.01379 | Approximate incremental PPR propagation | VERIFIED |
| 23 | STAG | 2023 | arXiv 2309.15875 (ICCD'23 per file name) | Additive incremental propagation; staleness | VERIFIED (arXiv); venue UNVERIFIED |
| 24 | D3-GNN | 2024 | PVLDB 17(11); arXiv 2409.09079 | Streaming GNN dataflow | VERIFIED |
| 25 | APAN | 2021 | SIGMOD; arXiv 2011.11545 | Asynchronous mailbox inference; Alipay fraud edges | VERIFIED |
| 26 | BRIGHT | 2022 | CIKM; DOI 10.1145/3511808.3557136 | Real-time Lambda GNN on transaction–entity graph | VERIFIED |
| 27 | GNNs in real-time fraud detection with Lambda architecture | 2021 | arXiv 2110.04559 | Earlier BRIGHT version | UNVERIFIED (not opened) |
| 28 | xFraud | 2022 | PVLDB 15(3); arXiv 2011.12193 | Shared-entity heterogeneous GNN plus explainer | VERIFIED |
| 29 | GEM (Malicious account detection) | 2018 | CIKM; arXiv 2002.12307 | Account–device bipartite; sum aggregation amplifies hubs | VERIFIED |
| 30 | FraudGT | 2024 | ICAIF | Edge gates and edge-attribute attention bias | VERIFIED |
| 31 | RioGNN | 2021 | TOIS; arXiv 2104.07886 | RL neighbour selection extending CARE-GNN | UNVERIFIED (single source) |
| 32 | DiG-In-GNN | 2024 | AAAI 38(8) | Guided RL neighbour selection | UNVERIFIED (single publisher source) |
| 33 | Barely Supervised Learning for Graph Fraud (BSL) | 2024 | AAAI | About 1% labels; consistency regularisation | VERIFIED |
| 34 | GraphConsis | 2020 | SIGIR; DOI 10.1145/3397271.3401253 | Consistency sampling; prunes hub products (>800 reviews) | VERIFIED |
| 35 | PMP: Partitioning Message Passing | 2024 | ICLR; arXiv 2412.00020 | Label-partitioned aggregation | VERIFIED |
| 36 | ConsisGAD | 2024 | ICLR | Limited supervision via consistency training | UNVERIFIED (mlanthology record only) |
| 37 | SpaceGNN | 2025 | ICLR; arXiv 2502.03201 | Extremely limited labels | VERIFIED |
| 38 | UniGAD | 2024 | NeurIPS; arXiv 2411.06427 | Multi-level (node/edge/graph) GAD via subgraph sampler | VERIFIED |
| 39 | MimbFD (message imbalance, dual view) | 2025 | IJCAI; arXiv 2507.06469 | Imbalance in aggregation | VERIFIED |
| 40 | DGA-GNN | 2024 | AAAI 38(10) | Dynamic grouping aggregation | VERIFIED |
| 41 | GFDN: Group-based Fraud Detection Network | 2023 | KDD | Group fraud with a GNN | VERIFIED |
| 42 | Gr-GAD: group-level GAD | 2023 | arXiv 2308.01063 | Unsupervised group anomaly detection | VERIFIED (arXiv) |
| 43 | GFM4GA | 2026 | arXiv 2601.10193 | Foundation model for group anomalies, few-shot | UNVERIFIED (single source) |
| 44 | SEFraud | 2024 | KDD (per paper); arXiv 2406.11389 | Self-explainable masks for fraud | VERIFIED (arXiv) |
| 45 | PinSage | 2018 | KDD; arXiv 1806.01973 | Top-T importance neighbours | VERIFIED |
| 46 | Multi-GNN (directed multigraphs) | 2024 | AAAI 38(10); arXiv 2306.11586 | AML subgraph patterns; minority F1 | VERIFIED |
| 47 | Elliptic++ | 2023 | arXiv 2306.06108 (ACM DOI; venue believed KDD 2023) | Bitcoin transaction and address graphs | VERIFIED (arXiv); venue UNVERIFIED |
| 48 | TravelFraudBench | 2026 | arXiv 2604.21093 | Ring-recovery benchmark; GraphSAGE best | VERIFIED (arXiv) |
| 49 | RGH-GNN: Risk-Gated Heterogeneous GNN | 2026 | arXiv 2610.27107 | LightGBM risk scores as edge weights gating aggregation | UNVERIFIED (arXiv page rate-limited; papers.cool and mirror read) |
| 50 | Fraud detection via graph clustering with heterogeneous link transformation | 2025 | arXiv 2512.19061 | Hard/soft link evidence; micro-batch updates; rings | UNVERIFIED |
| 51 | PromoGuardian | 2026 | IEEE S&P; arXiv 2510.12652 | Conjunctive edges, co-occurrence weights, groups | VERIFIED |
| 52 | Detecting Fake Reviewer Groups in Dynamic Networks | 2026 | arXiv 2603.08332 | Dynamic group detection; no incremental exactness | VERIFIED (arXiv) |
| 53 | L2IR | 2026 | arXiv 2605.26040 | Pseudo-label self-training plus edge audit | UNVERIFIED |
| 54 | DeFraudNet | 2021 | ECML-PKDD | Snorkel weak labels plus GCN | UNVERIFIED |
| 55 | CleverCatch | 2025 | arXiv 2510.13205 | Rule-guided weak supervision (no graph) | VERIFIED (arXiv) |
| 56 | WSNET: Weak Supervision for Real World Graphs | 2025 | arXiv 2506.02451 | Graph weak supervision (non-fraud) | UNVERIFIED |
| 57 | LaundroGraph | 2022 | ICAIF | Self-supervised AML graph | UNVERIFIED |
| 58 | GTAN: Semi-supervised credit card fraud via attribute-driven graph | 2024 | arXiv 2412.18287 | Few labels; gated temporal attention | UNVERIFIED |
| 59 | Rule-anchored graph learning (synthetic identity) | 2026 | Discover Informatics | Rule plus HGT fusion; rules stay the backbone | UNVERIFIED |
| 60 | Money-mule detection on RBIH NFPC | 2026 | arXiv 2610.21314 | Featureless address/PIN hub nodes; account-level | UNVERIFIED |
| 61 | How Faithful are Self-Explainable GNNs? | 2023 | arXiv 2308.15096 | SE-GNNs are not faithful by design | VERIFIED (arXiv) |
| 62 | Reconsidering Faithfulness (Azzolin et al.) | 2025 | ICLR | Leakage; conditions for faithful SE-GNNs | VERIFIED |
| 63 | HGT-FD: Hypergraph Transformer for Fraud Detection | 2026 | AISTATS, PMLR 300 | Hyperedges (shared attributes as hyperedges plausible; n/s) | VERIFIED |
| 64 | Identifying Linked Fraudulent Activities Using GCN | 2021 | arXiv 2106.04513 | Account edges from shared cookie/device | UNVERIFIED |
| 65 | GNN with One-side Edge Sampling | 2026 | arXiv 2601.06800 | Confidence-based edge sampling on AMLworld | UNVERIFIED |
| 66 | AML with Unreliable Labels (MSc thesis, Chalmers) | 2024 | Thesis | Weakly supervised GNN for AML | VERIFIED (thesis record + project page) |
| 67 | Graph Pre-Training Models Are Strong Anomaly Detectors | 2024 | arXiv 2410.18487 | Limited-label GAD | UNVERIFIED (not opened) |
| 68 | GDN: Alleviating Structural Distribution Shift in GAD | 2023 | WSDM; arXiv 2401.14155 | Heterophily shift | UNVERIFIED (not opened) |
| 69 | Graph-Based Fraud Detection with Dual-Path Graph Filtering | 2026 | arXiv 2604.14235 | Similarity graph plus filters | UNVERIFIED |

Also noted but not counted: Amatriciana (temporal GNN for AML, arXiv 2506.00654), Omega (GNN serving, arXiv 2501.08547), the Alibaba GraphScope Dynamic Graph Sampling Service blog (event-driven pre-sampling with reservoir sampling), and TMR-GGNN (arXiv 2606.18444). All UNVERIFIED and not opened, except the GraphScope blog.

---

## 4. Top-5 closest to EvidGNN

1. **PromoGuardian (IEEE S&P 2026).**
   - Already does: builds user–user edges only when two conditions co-occur (same product the same day **and** a shared relation value). This is a conjunctive "second evidence" rule. It also gives edges multi-relation features scaled by co-occurrence weights, trains a GNN with few labels plus seed propagation, and targets groups.
   - Left: no hub discount by degree. The conjunction is applied once at graph construction, not as a gate inside message passing through attribute nodes. Batch processing is daily, with no incremental exactness and no explanations.
2. **Spade (PVLDB 16, 2022).**
   - Already does: streaming fraud-community detection on Grab data, a FRAUDAR-style 1/log(x+c) degree weight, incremental peeling proved equal to static peeling, and benign/urgent edge batching.
   - Left: no learned model. It uses no shared-attribute pair evidence and no labels, and its output is dense subgraphs, not GNN scores. It is the closest analogue to the paper's rule engine and should be cited prominently.
3. **CARE-GNN, with RioGNN, PC-GNN and GraphConsis.**
   - Already does: camouflage-resistant neighbour selection on shared-attribute relations, using top-p by label-aware learned similarity. GraphConsis prunes hub products with more than 800 reviews and samples in proportion to consistency.
   - Left: selection is learned from labels and features, not from label-free structural pair evidence. There is no discount by hub degree, no requirement for corroborating evidence, and no streaming.
4. **Exact incremental GNN inference: InkStream, with RIPPLE, NrtInc and StreamTGN.**
   - Already does: recomputes only the affected or dirty L-hop region. They claim, prove (NrtInc Theorem 1) or test (NrtInc MSE < 1e-4; StreamTGN identical AP/AUC) equality with full recomputation. InkStream explicitly sketches sampling support by caching samples and applying the differences as edge updates.
   - Left: none of them handles neighbour sets that depend on the data. When a hub's degree changes, h(d) changes for every pair through that hub, which changes their top-k selections. None is fraud-specific or produces rings.
5. **FraudGT (ICAIF 2024).**
   - Already does: sigmoid edge-feature gates on messages plus an edge-attribute attention bias, for financial fraud on AMLworld. This is essentially the "soft variant" of Component 1.
   - Left: its edge features are raw transaction attributes, not derived pairwise evidence over shared attributes. It has no hub handling, no hard gate, no streaming and no weak supervision.

Runners-up: BRIGHT and xFraud (shared-entity heterogeneous graphs and real-time serving at eBay, no hub gate); TravelFraudBench (ring recovery; GraphSAGE wins on the projected graph, which matches the paper's own finding); RGH-GNN (risk-score-gated aggregation, Oct 2026).

---

## 5. Novelty-risk memo

### Component 1 — Evidence-gated message passing and evidence-aware sampling: **PARTLY DONE (state the difference)**
- **Soft variant (W as edge feature or attention bias): already done in form (cite and reposition).**
  - FraudGT has edge gates G_ij=σ(E'_ij W_G) and an attention bias b_ij.
  - RGH-GNN uses LightGBM risk scores as edge weights in a learnable risk-gated aggregation.
  - PinSage uses importance pooling.
  - The only new element is the content of the edge feature: W, a label-free, hub-discounted, decayed pair evidence score.
- **Evidence-aware top-k sampling: partly done.**
  - PinSage keeps the top-T neighbours by random-walk importance.
  - CARE-GNN keeps the top-p by learned similarity.
  - GraphConsis samples in proportion to consistency, and PC-GNN uses its pick/choose samplers.
  - Difference: the ranking score is structural, label-free and fraud-specific (h(deg a)·decay plus a capped transfer term), and it is deterministic, which Component 2 needs.
- **Hard gate ("a hub never links a pair alone" inside MP): no direct prior found.**
  - The nearest is PromoGuardian's conjunctive edge construction.
  - The FRAUDAR/Spade column weighting addresses camouflage for peeling, not for GNN messages.
  - GraphConsis drops hubs entirely.
  - Risk: a reviewer can say the hard gate is graph preprocessing followed by a standard GNN on a projected user–user graph; TravelFraudBench's projection and PromoGuardian's edges already work this way. To be novel, the paper needs either (a) a camouflage-resistance statement for messages, analogous to FRAUDAR Thm 4.4, or (b) gating applied per layer on the bipartite user–attribute graph with an ablation showing it beats prune-then-GNN.

### Component 2 — Exact incremental GNN inference: **ALREADY DONE (cite and reposition)**
- InkStream, RIPPLE, NrtInc, StreamTGN and STAG already recompute only the affected region with exactness claims, a theorem (NrtInc) or tests (NrtInc, StreamTGN). Spade does the same for degree-weighted peeling.
- Remaining delta:
  - Neighbour selection here depends on the data: deterministic top-k by W, where W depends on attribute degrees. One insertion into a hub changes h(d) for every pair through it, so the dirty set must include every node whose selected set changes. That can be much larger than the L-hop region of the new edges.
  - A proof and test that cover this case would be a modest, honest contribution.
- Do not headline this as novel. Present it as "we inherit exact incremental inference [InkStream; RIPPLE; NrtInc] and extend the dirty-set rule to evidence-ranked neighbourhoods."

### Component 3 — Label-efficient training on rule-pipeline pseudo-labels: **PARTLY DONE (state the difference)**
- Weak labels from rules and heuristics with a GCN: DeFraudNet (Snorkel).
- Pseudo-label self-training on fraud graphs: L2IR. Seeds plus group propagation: PromoGuardian.
- Few-label GAD: BSL, ConsisGAD, SpaceGNN.
- Rules fused with an HGT: the 2026 Discover Informatics paper.
- Not found: a GNN trained on ring-level outputs of a deterministic streaming rule pipeline, compared against gold labels across label budgets. The gap is real but methodologically incremental. Its value rests on the experiment: budget curves, label-noise analysis, and whether the student exceeds its teacher.

### Optional — Ring-level scorer restricted to evidence edges ("explanation is the computation"): **PARTLY DONE (state the difference)**
- Group or ring-level GNNs exist (GFDN, UniGAD, Gr-GAD, GFM4GA), and so do self-explainable fraud GNNs (SEFraud).
- Azzolin et al. (ICLR 2025) and Christiansen et al. (2023) show that "faithful by design" claims often fail because of leakage. Faithfulness needs hard selection, readout restricted to the explanation, and local aggregation.
- Difference: the explanation subgraph is fixed before learning (the evidence edges), so faithfulness reduces to the absence of leakage, which can be checked. The claim must still be backed by deletion (Fid+/Fid−) tests, not asserted.

---

## 6. Draft positioning sentences

**Component 1.**
- Prior camouflage-resistant GNNs select neighbours with similarity learned from labels (CARE-GNN, PC-GNN, GraphConsis). Our gate is label-free and structural: a message crosses a busy shared attribute only when the pair has a second, independent piece of evidence.
- Edge-feature gates and attention biases are established (FraudGT; RGH-GNN). We use the same mechanism but feed it a pairwise evidence score W whose hub discount follows FRAUDAR-style column weighting.
- Unlike conjunctive edge construction applied once before training (PromoGuardian), the gate is applied at every layer on the user–attribute graph. We compare it directly against prune-then-GNN.

**Component 2.**
- Exact incremental GNN inference over affected regions is known (InkStream; RIPPLE; NrtInc; StreamTGN). We adopt it and extend the dirty-set rule to neighbourhoods selected deterministically by evidence, where a change in a hub's degree reweights every pair through that hub.
- Like Spade for degree-weighted peeling, we prove the incremental output equals full recomputation. We also test it bit-for-bit on every micro-batch.

**Component 3.**
- Weak supervision for fraud graphs usually comes from labelling functions or self-training (DeFraudNet; L2IR). We instead distil the confirmed rings of a deterministic streaming rule pipeline and measure how far the student exceeds its teacher across gold-label budgets.
- Few-label GAD methods (BSL, ConsisGAD, SpaceGNN) assume a small set of gold labels. Our setting has none at deployment, only rule outputs.

**Ring scorer (optional).**
- Group-level detectors (GFDN, UniGAD) score candidate groups with unrestricted message passing. Our scorer sees only evidence edges, so its explanation is its input. Following Azzolin et al., we verify faithfulness with deletion tests rather than asserting it.

**Draft related-work paragraph.**
Graph fraud detectors have handled camouflage in three ways. The first is reweighting by degree in dense-subgraph mining: FRAUDAR's column weighting and its streaming, exact-incremental form in Spade. The second is learning which neighbours to trust in multi-relation GNNs: CARE-GNN, PC-GNN, GraphConsis and successors such as PMP and DGA-GNN, benchmarked in GADBench, where tree ensembles with neighbour aggregation remain strong. The third is conditioning messages on edge features: FraudGT's edge gates and attention bias, and risk-gated aggregation in RGH-GNN. Industrial systems link transactions or accounts through shared entities (GEM, xFraud, BRIGHT), and PromoGuardian builds user edges only when two relations co-occur. None of these routes a message through a busy shared attribute only when the pair has corroborating evidence, using a label-free hub discount. Exact incremental GNN inference is now well studied (InkStream, RIPPLE, NrtInc, StreamTGN). We reuse it and extend the dirty-set argument to evidence-ranked neighbourhoods. For supervision, prior work uses labelling functions (DeFraudNet), self-training (L2IR) or few gold labels (BSL, ConsisGAD). We instead distil the outputs of a rule pipeline. Finally, group-level detectors (GFDN, UniGAD) and self-explainable fraud GNNs (SEFraud) exist, but recent evidence shows faithfulness must be tested, not assumed (Azzolin et al., 2025).

---

## 7. BibTeX (VERIFIED only)

```bibtex
% VERIFY
@inproceedings{dou2020care,
  title={Enhancing Graph Neural Network-based Fraud Detectors against Camouflaged Fraudsters},
  author={Dou, Yingtong and Liu, Zhiwei and Sun, Li and Deng, Yutong and Peng, Hao and Yu, Philip S.},
  booktitle={Proceedings of the 29th ACM International Conference on Information and Knowledge Management (CIKM)},
  year={2020}, note={arXiv:2008.08692}
}
% VERIFY
@inproceedings{tang2022bwgnn,
  title={Rethinking Graph Neural Networks for Anomaly Detection},
  author={Tang, Jianheng and Li, Jiajin and Gao, Ziqi and Li, Jia},
  booktitle={Proceedings of the 39th International Conference on Machine Learning (ICML)},
  series={PMLR}, volume={162}, pages={21076--21089}, year={2022}
}
% VERIFY
@inproceedings{tang2023gadbench,
  title={{GADBench}: Revisiting and Benchmarking Supervised Graph Anomaly Detection},
  author={Tang, Jianheng and Hua, Fengrui and Gao, Ziqi and Zhao, Peilin and Li, Jia},
  booktitle={Advances in Neural Information Processing Systems 36 (Datasets and Benchmarks Track)},
  year={2023}
}
% VERIFY
@inproceedings{hamilton2017graphsage,
  title={Inductive Representation Learning on Large Graphs},
  author={Hamilton, Will and Ying, Zhitao and Leskovec, Jure},
  booktitle={Advances in Neural Information Processing Systems 30},
  year={2017}
}
% VERIFY
@inproceedings{ying2019gnnexplainer,
  title={{GNNExplainer}: Generating Explanations for Graph Neural Networks},
  author={Ying, Zhitao and Bourgeois, Dylan and You, Jiaxuan and Zitnik, Marinka and Leskovec, Jure},
  booktitle={Advances in Neural Information Processing Systems 32},
  year={2019}
}
% VERIFY  (author order from CMU ML news page)
@inproceedings{hooi2016fraudar,
  title={{FRAUDAR}: Bounding Graph Fraud in the Face of Camouflage},
  author={Hooi, Bryan and Song, Hyun Ah and Beutel, Alex and Shah, Neil and Shin, Kijung and Faloutsos, Christos},
  booktitle={Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (KDD)},
  year={2016}, doi={10.1145/2939672.2939747}
}
% VERIFY  (author order from the TKDD PDF; DOI from search listing)
@article{hooi2017camouflage,
  title={Graph-Based Fraud Detection in the Face of Camouflage},
  author={Hooi, Bryan and Shin, Kijung and Song, Hyun Ah and Beutel, Alex and Shah, Neil and Faloutsos, Christos},
  journal={ACM Transactions on Knowledge Discovery from Data},
  volume={11}, number={4}, pages={44}, year={2017}, doi={10.1145/3056563}
}
% VERIFY
@article{jiang2022spade,
  title={Spade: A Real-Time Fraud Detection Framework on Evolving Graphs},
  author={Jiang, Jiaxin and Li, Yuan and He, Bingsheng and Hooi, Bryan and Chen, Jia and Kang, Johan Kok Zhi},
  journal={Proceedings of the VLDB Endowment}, volume={16}, number={3}, year={2022}
}
% VERIFY
@inproceedings{altman2023amlworld,
  title={Realistic Synthetic Financial Transactions for Anti-Money Laundering Models},
  author={Altman, Erik and Blanu{\v{s}}a, Jovan and von Niederh{\"a}usern, Luc and Egressy, Beni and Anghel, Andreea and Atasu, Kubilay},
  booktitle={Advances in Neural Information Processing Systems 36 (Datasets and Benchmarks Track)},
  year={2023}
}
% VERIFY
@inproceedings{huang2022dgraph,
  title={{DGraph}: A Large-Scale Financial Dataset for Graph Anomaly Detection},
  author={Huang, Xuanwen and Yang, Yang and Wang, Yang and Wang, Chunping and Zhang, Zhisheng and Xu, Jiarong and Chen, Lei and Vazirgiannis, Michalis},
  booktitle={Advances in Neural Information Processing Systems 35 (Datasets and Benchmarks Track)},
  year={2022}
}
% VERIFY
@inproceedings{jesus2022baf,
  title={Turning the Tables: Biased, Imbalanced, Dynamic Tabular Datasets for {ML} Evaluation},
  author={Jesus, S{\'e}rgio and Pombal, Jos{\'e} and Alves, Duarte and Cruz, Andr{\'e} and Saleiro, Pedro and Ribeiro, Rita and Gama, Jo{\~a}o and Bizarro, Pedro},
  booktitle={Advances in Neural Information Processing Systems 35 (Datasets and Benchmarks Track)},
  year={2022}
}
% VERIFY  (venue believed WWW 2023; confirm before citing as conference paper; full author list to confirm)
@misc{wang2023gaga,
  title={Label Information Enhanced Fraud Detection against Low Homophily in Graphs},
  author={Wang, Yuchen and Zhang, Jinghui and others},
  year={2023}, eprint={2302.10407}, archivePrefix={arXiv}
}
% VERIFY  (arXiv; a later version may be at IPDPS 2025)
@misc{wu2023inkstream,
  title={{InkStream}: Real-time {GNN} Inference on Streaming Graphs via Incremental Update},
  author={Wu, Dan and Li, Zhaoying and Mitra, Tulika},
  year={2023}, eprint={2309.11071}, archivePrefix={arXiv}
}
% VERIFY
@inproceedings{naman2025ripple,
  title={{RIPPLE}: Scalable Incremental {GNN} Inferencing on Large Streaming Graphs},
  author={Naman, Pranjal and Simmhan, Yogesh},
  booktitle={45th IEEE International Conference on Distributed Computing Systems (ICDCS)},
  year={2025}, note={arXiv:2505.12112}
}
% VERIFY
@misc{naman2026rippleplus,
  title={{RIPPLE++}: An Incremental Framework for Efficient {GNN} Inference on Evolving Graphs},
  author={Naman, Pranjal and Agarwal, Parv and Haritas, Hrishikesh and Simmhan, Yogesh},
  year={2026}, eprint={2601.12347}, archivePrefix={arXiv}
}
% VERIFY
@misc{wang2026nrtinc,
  title={Incremental {GNN} Embedding Computation on Streaming Graphs},
  author={Wang, Qiange and Lv, Haoran and Zhang, Yanfeng and Wong, Weng-Fai and He, Bingsheng},
  year={2026}, eprint={2603.20622}, archivePrefix={arXiv}
}
% VERIFY
@misc{zhang2026streamtgn,
  title={{StreamTGN}: A {GPU}-Efficient Serving System for Streaming Temporal Graph Neural Networks},
  author={Zhang, Lingling and Qiao, Pengpeng and Zhang, Zhiwei and Yuan, Ye and Wang, Guoren},
  year={2026}, eprint={2603.21090}, archivePrefix={arXiv}
}
% VERIFY
@inproceedings{zheng2022instantgnn,
  title={Instant Graph Neural Networks for Dynamic Graphs},
  author={Zheng, Yanping and Wang, Hanzhi and Wei, Zhewei and Liu, Jiajun and Wang, Sibo},
  booktitle={Proceedings of the 28th ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  year={2022}, note={arXiv:2206.01379}
}
% VERIFY  (venue ICCD 2023 unconfirmed)
@misc{wang2023stag,
  title={{STAG}: Enabling Low Latency and Low Staleness of {GNN}-based Services with Dynamic Graphs},
  author={Wang, Jiawen and Chen, Quan and Zeng, Deze and Song, Zhuo and Chen, Chen and Guo, Minyi},
  year={2023}, eprint={2309.15875}, archivePrefix={arXiv}
}
% VERIFY  (year inferred from PVLDB vol. 17)
@article{guliyev2024d3gnn,
  title={{D3-GNN}: Dynamic Distributed Dataflow for Streaming Graph Neural Networks},
  author={Guliyev, Rustam and Haldar, Aparajita and Ferhatosmanoglu, Hakan},
  journal={Proceedings of the VLDB Endowment}, volume={17}, number={11}, year={2024}
}
% VERIFY
@inproceedings{wang2021apan,
  title={{APAN}: Asynchronous Propagation Attention Network for Real-time Temporal Graph Embedding},
  author={Wang, Xuhong and Lyu, Ding and Li, Mengjian and Xia, Yang and Yang, Qi and Wang, Xinwen and Wang, Xinguang and Cui, Ping and Yang, Yupu and Sun, Bowen and Guo, Zhenyu},
  booktitle={Proceedings of the 2021 International Conference on Management of Data (SIGMOD)},
  year={2021}
}
% VERIFY
@inproceedings{lu2022bright,
  title={{BRIGHT} -- Graph Neural Networks in Real-time Fraud Detection},
  author={Lu, Mingxuan and Han, Zhichao and Rao, Susie Xi and Zhang, Zitao and Zhao, Yang and Shan, Yinan and Raghunathan, Ramesh and Zhang, Ce and Jiang, Jiawei},
  booktitle={Proceedings of the 31st ACM International Conference on Information \& Knowledge Management (CIKM)},
  pages={3342--3351}, year={2022}, doi={10.1145/3511808.3557136}
}
% VERIFY
@article{rao2022xfraud,
  title={{xFraud}: Explainable Fraud Transaction Detection},
  author={Rao, Susie Xi and Zhang, Shuai and Han, Zhichao and Zhang, Zitao and Min, Wei and Chen, Zhiyao and Shan, Yinan and Zhao, Yang and Zhang, Ce},
  journal={Proceedings of the VLDB Endowment}, volume={15}, number={3}, year={2022}
}
% VERIFY
@inproceedings{liu2018gem,
  title={Heterogeneous Graph Neural Networks for Malicious Account Detection},
  author={Liu, Ziqi and Chen, Chaochao and Yang, Xinxing and Zhou, Jun and Li, Xiaolong and Song, Le},
  booktitle={Proceedings of the 27th ACM International Conference on Information and Knowledge Management (CIKM)},
  year={2018}
}
% VERIFY
@inproceedings{lin2024fraudgt,
  title={{FraudGT}: A Simple, Effective, and Efficient Graph Transformer for Financial Fraud Detection},
  author={Lin, Junhong and Guo, Xiaojie and Zhu, Yada and Mitchell, Samuel and Altman, Erik and Shun, Julian},
  booktitle={Proceedings of the 5th ACM International Conference on AI in Finance (ICAIF)},
  year={2024}
}
% VERIFY
@inproceedings{yu2024bsl,
  title={Barely Supervised Learning for Graph-Based Fraud Detection},
  author={Yu, Hang and Liu, Zhengyang and Luo, Xiangfeng},
  booktitle={Proceedings of the AAAI Conference on Artificial Intelligence (AAAI-24)},
  year={2024}
}
% VERIFY
@inproceedings{liu2020graphconsis,
  title={Alleviating the Inconsistency Problem of Applying Graph Neural Network to Fraud Detection},
  author={Liu, Zhiwei and Dou, Yingtong and Yu, Philip S. and Deng, Yutong and Peng, Hao},
  booktitle={Proceedings of the 43rd International ACM SIGIR Conference},
  year={2020}, doi={10.1145/3397271.3401253}
}
% VERIFY
@inproceedings{zhuo2024pmp,
  title={Partitioning Message Passing for Graph Fraud Detection},
  author={Zhuo, Wei and Liu, Zemin and Hooi, Bryan and He, Bingsheng and Tan, Guang and Fathony, Rizal and Chen, Jia},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2024}
}
% VERIFY
@inproceedings{dong2025spacegnn,
  title={{SpaceGNN}: Multi-Space Graph Neural Network for Node Anomaly Detection with Extremely Limited Labels},
  author={Dong, Xiangyu and Zhang, Xingyi and Chen, Lei and Yuan, Mingxuan and Wang, Sibo},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2025}
}
% VERIFY
@inproceedings{lin2024unigad,
  title={{UniGAD}: Unifying Multi-level Graph Anomaly Detection},
  author={Lin, Yiqing and Tang, Jianheng and Zi, Chenyi and Zhao, H. Vicky and Yao, Yuan and Li, Jia},
  booktitle={Advances in Neural Information Processing Systems 37},
  year={2024}
}
% VERIFY
@inproceedings{song2025mimbfd,
  title={Mitigating Message Imbalance in Fraud Detection with Dual-View Graph Representation Learning},
  author={Song, Yudan and Wei, Yuecen and Lu, Yuhang and Sun, Qingyun and Shao, Minglai and Wang, Li-e and Hu, Chunming and Li, Xianxian and Fu, Xingcheng},
  booktitle={Proceedings of the 34th International Joint Conference on Artificial Intelligence (IJCAI)},
  pages={3281--3289}, year={2025}
}
% VERIFY
@inproceedings{duan2024dgagnn,
  title={{DGA-GNN}: Dynamic Grouping Aggregation {GNN} for Fraud Detection},
  author={Duan, Mingjiang and Zheng, Tongya and Gao, Yang and Wang, Gang and Feng, Zunlei and Wang, Xinyu},
  booktitle={Proceedings of the AAAI Conference on Artificial Intelligence}, volume={38}, number={10},
  pages={11820--11828}, year={2024}
}
% VERIFY
@inproceedings{yu2023gfdn,
  title={Group-based Fraud Detection Network on e-Commerce Platforms},
  author={Yu, Jianke and Wang, Hanchen and Wang, Xiaoyang and Li, Zhao and Qin, Lu and Zhang, Wenjie and Liao, Jian and Zhang, Ying},
  booktitle={Proceedings of the 29th ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  pages={5463--5475}, year={2023}
}
% VERIFY
@misc{ai2023grgad,
  title={Graph Anomaly Detection at Group Level: A Topology Pattern Enhanced Unsupervised Approach},
  author={Ai, Xing and Zhou, Jialong and Zhu, Yulin and Li, Gaolei and Michalak, Tomasz P. and Luo, Xiapu and Zhou, Kai},
  year={2023}, eprint={2308.01063}, archivePrefix={arXiv}
}
% VERIFY  (venue KDD 2024 stated in preprint)
@misc{li2024sefraud,
  title={{SEFraud}: Graph-based Self-Explainable Fraud Detection via Interpretative Mask Learning},
  author={Li, Kaidi and Yang, Tianmeng and Zhou, Min and Meng, Jiahao and Wang, Shendi and Wu, Yihui and Tan, Boshuai and Song, Hu and Pan, Lujia and Yu, Fan and Sheng, Zhenli and Tong, Yunhai},
  year={2024}, eprint={2406.11389}, archivePrefix={arXiv}
}
% VERIFY
@inproceedings{ying2018pinsage,
  title={Graph Convolutional Neural Networks for Web-Scale Recommender Systems},
  author={Ying, Rex and He, Ruining and Chen, Kaifeng and Eksombatchai, Pong and Hamilton, William L. and Leskovec, Jure},
  booktitle={Proceedings of the 24th ACM SIGKDD International Conference on Knowledge Discovery \& Data Mining (KDD)},
  year={2018}
}
% VERIFY
@inproceedings{egressy2024multignn,
  title={Provably Powerful Graph Neural Networks for Directed Multigraphs},
  author={Egressy, B{\'e}ni and von Niederh{\"a}usern, Luc and Blanu{\v{s}}a, Jovan and Altman, Erik and Wattenhofer, Roger and Atasu, Kubilay},
  booktitle={Proceedings of the AAAI Conference on Artificial Intelligence}, volume={38}, number={10},
  pages={11838--11846}, year={2024}
}
% VERIFY  (venue believed KDD 2023; DOI 10.1145/3580305.3599803)
@misc{elmougy2023ellipticpp,
  title={Demystifying Fraudulent Transactions and Illicit Nodes in the Bitcoin Network for Financial Forensics},
  author={Elmougy, Youssef and Liu, Ling},
  year={2023}, eprint={2306.06108}, archivePrefix={arXiv}
}
% VERIFY
@misc{sajja2026travelfraudbench,
  title={{TravelFraudBench}: A Configurable Evaluation Framework for {GNN} Fraud Ring Detection in Travel Networks},
  author={Sajja, Bhavana},
  year={2026}, eprint={2604.21093}, archivePrefix={arXiv}
}
% VERIFY
@inproceedings{li2026promoguardian,
  title={{PromoGuardian}: Detecting Promotion Abuse Fraud with Multi-Relation Fused Graph Neural Networks},
  author={Li, Shaofei and Han, Xiao and Zhang, Ziqi and Liang, Zhenkai and Guo, Yao and Chen, Xiangqun and Li, Ding and Gao, Shuli and Hua, Minyao},
  booktitle={47th IEEE Symposium on Security and Privacy (S\&P)},
  year={2026}, note={arXiv:2510.12652}
}
% VERIFY
@misc{zhang2026fakegroups,
  title={Detecting Fake Reviewer Groups in Dynamic Networks: An Adaptive Graph Learning Method},
  author={Zhang, Jing and Huang, Ke and Zhang, Yao and Guo, Bin and Yu, Zhiwen},
  year={2026}, eprint={2603.08332}, archivePrefix={arXiv}
}
% VERIFY
@misc{mozafari2025clevercatch,
  title={{CleverCatch}: A Knowledge-Guided Weak Supervision Model for Fraud Detection},
  author={Mozafari, Amirhossein and Hashemi, Kourosh and Shafagh, Erfan and Motamedi, Soroush and Tayebi, Azar Taheri and Tayebi, Mohammad A.},
  year={2025}, eprint={2510.13205}, archivePrefix={arXiv}
}
% VERIFY
@misc{christiansen2023faithful,
  title={How Faithful are Self-Explainable {GNNs}?},
  author={Christiansen, Marc and Villadsen, Lea and Zhong, Zhiqiang and Teso, Stefano and Mottin, Davide},
  year={2023}, eprint={2308.15096}, archivePrefix={arXiv}
}
% VERIFY
@inproceedings{azzolin2025faithfulness,
  title={Reconsidering Faithfulness in Regular, Self-Explainable and Domain Invariant {GNNs}},
  author={Azzolin, Steve and Longa, Antonio and Teso, Stefano and Passerini, Andrea},
  booktitle={International Conference on Learning Representations (ICLR)},
  year={2025}
}
% VERIFY
@inproceedings{cai2026hgtfd,
  title={{HGT-FD}: Hypergraph Transformer for Fraud Detection},
  author={Cai, Yintao and Liu, Yunjiong and Yang, Zelong and Fang, Shuyang and Min, Xiaoping},
  booktitle={Proceedings of the 29th International Conference on Artificial Intelligence and Statistics (AISTATS)},
  series={PMLR}, volume={300}, pages={4996--5004}, year={2026}
}
% VERIFY
@mastersthesis{bergquist2024aml,
  title={Anti-Money Laundering with Unreliable Labels},
  author={Bergquist, Jesper},
  school={Chalmers University of Technology}, year={2024}
}
% VERIFY
@article{jiang2024spadedemo,
  title={Spade: A Real-Time Fraud Detection Framework},
  author={Jiang, Jiaxin and Zhang, Zhen and Luo, Bingqiao and He, Bingsheng and Chen, Min and Wang, WeiYang and Chen, Jia},
  journal={Proceedings of the VLDB Endowment}, volume={17}, number={12}, pages={4253--4256}, year={2024}
}
```

---

## 8. Queries and URLs

### Queries (mode; approximate number of relevant hits)
1. CARE-GNN Enhancing Graph Neural Network-based Fraud Detectors against Camouflaged Fraudsters CIKM 2020 (std; 3)
2. PC-GNN Pick and Choose imbalanced fraud detection WWW 2021 (std; 2)
3. Rethinking Graph Neural Networks for Anomaly Detection BWGNN ICML 2022 (std; 4)
4. GADBench Revisiting and Benchmarking Supervised Graph Anomaly Detection NeurIPS 2023 (std; 4)
5. dblp Pick and Choose GNN-based Imbalanced Learning Approach Fraud Detection Liu Ao Sun (std; 2)
6. "Pick and Choose" GNN imbalanced fraud detection Yang Liu Xiang Ao Web Conference 2021 doi … (std; 2)
7. FRAUDAR Bounding Graph Fraud in the Face of Camouflage KDD 2016 Hooi (std; 5)
8. Spade real-time fraud detection evolving graphs PVLDB Jiang (std; 4)
9. Realistic Synthetic Financial Transactions for Anti-Money Laundering Models Altman NeurIPS 2023 (std; 4)
10. InkStream real-time GNN inference streaming graphs incremental update (std; 4)
11. Ripple scalable incremental GNN inferencing large streaming graphs (std; 4)
12. incremental GNN inference affected nodes exact equivalence full recomputation dynamic graph (std; 5)
13. online GNN inference caching embeddings edge insertion low latency fraud (std; 3)
14. GHRN Addressing Heterophily in Graph Anomaly Detection … WWW 2023 (std; 1)
15. H2-FDetector heterophily homophily fraud detection WWW 2022 (std; 1)
16. GAGA label information enhanced fraud detection group aggregation VLDB 2023 (std; 2)
17. graph fraud detection high-degree nodes hub GNN 2024 2025 (std; 1)
18. Tang Addressing heterophily graph anomaly detection perspective graph spectrum GHRN … (std; 1)
19. camouflaged fraudster GNN neighbour filtering reinforcement learning relation-aware 2024 (std; 3)
20. label-aware neighbour sampling graph fraud detection imbalance sampler (std; 2)
21. degree-aware aggregation graph anomaly detection high-degree normal nodes dilution (std; 1)
22. BRIGHT graph neural networks in real-time fraud detection CIKM 2022 eBay (std; 3)
23. xFraud explainable fraud transaction detection heterogeneous graph VLDB (std; 3)
24. Heterogeneous Graph Neural Networks for Malicious Account Detection GEM device account Alipay CIKM 2018 (std; 2)
25. edge weighted gated message passing fraud detection shared attribute multi-relation GNN (std; 2)
26. FraudGT graph transformer financial fraud detection edge-based message passing gates arXiv (std; 3)
27. weak supervision rules pseudo-labels graph neural network fraud detection (std; 4)
28. rule-guided GNN fraud detection expert rules knowledge distillation (std; 2)
29. fraud ring detection graph neural network group-level (std; 1)
30. anti-money laundering GNN trained on rule-based alerts noisy labels pseudo-labels transaction graph (std; 2)
31. semi-supervised graph fraud detection few labels label budget pseudo-labeling 2024 2025 (std; 4)
32. group anomaly detection graph neural network fraud groups gang detection 2024 (std; 2)
33. self-explainable graph neural network fraud detection SEFraud (std; 2)
34. PinSage importance-based neighborhoods top-T random walk visit counts Ying KDD 2018 (std; 1)
35. GNN explanation faithfulness fidelity deletion evaluation graph anomaly detection (std; 3)
36. APAN asynchronous propagation attention network real-time temporal graph embedding SIGMOD 2021 fraud (std; 1)
37. Instant Graph Neural Networks for Dynamic Graphs KDD 2022 Zheng (std; 1)
38. streaming graph neural network inference dirty region recompute only affected neighbours micro-batch (ext; 4)
39. temporal GNN fraud detection streaming real-time transactions dynamic graph 2025 (std; 3)
40. Partitioning Message Passing for Graph Fraud Detection ICLR 2024 (std; 1)
41. ConsisGAD consistency training graph anomaly detection limited supervision ICLR 2024 (std; 3)
42. UniGAD unifying multi-level graph anomaly detection NeurIPS 2024 (std; 1)
43. Mitigating Message Imbalance in Fraud Detection with Dual-View Graph Representation Learning (std; 1)
44. GNN fraud detection shared device IP high-degree attribute nodes downweight or remove supernodes account linking (ext; 1)
45. evidence-aware neighbor sampling top-k edge weight deterministic GNN sampler fraud (ext; 2)
46. PC-GNN github PonderLY Pick and Choose fraud detection code (std; 1 — TravelFraudBench)
47. Multi-GNN provably powerful graph neural networks directed multigraphs anti-money laundering Egressy AAAI 2024 (std; 1)
48. DGraph large-scale financial dataset graph anomaly detection NeurIPS 2022 Huang (std; 1)
49. Turning the Tables … Bank Account Fraud NeurIPS 2022 (std; 1)
50. Elliptic++ dataset Demystifying Fraudulent Transactions … KDD 2023 (std; 1)
51. Inductive Representation Learning on Large Graphs Hamilton Ying Leskovec NeurIPS 2017 proceedings (std; 1)
52. GNNExplainer Generating Explanations for Graph Neural Networks NeurIPS 2019 proceedings (std; 1)
53. self-interpretable GNN explanation is the computation subgraph faithful by construction (std; 3)
54. fraud ring detection streaming graph incremental GNN money mule ring 2025 arXiv (ext; 2)
55. hypergraph neural network fraud detection shared attributes hyperedges large hyperedge (std; 2)
56. GraphConsis alleviating inconsistency problem applying graph neural network fraud detection SIGIR 2020 (std; 1)
57. graph neural network account linking number of shared identifiers edge weight co-occurrence multiple shared attributes fraud (ext; 2)
58. RGH-GNN Risk-Gated Heterogeneous Graph Neural Network Financial Fraud Detection (std; 0)
59. GDN alleviating structural distribution shift graph anomaly detection WSDM 2023 (std; 1)
60. SpaceGNN extremely limited labels node anomaly detection ICLR 2025 (std; 1)
61. Graph Pre-Training Models Are Strong Anomaly Detectors limited labels (std; 1)
62. D3-GNN dynamic distributed dataflow streaming GNN VLDB 2024 (std; 1)
63. DGA-GNN dynamic grouping aggregation fraud detection AAAI 2024 (std; 2)
64. Amatriciana temporal GNN money laundering detection (std; 1)
65. label noise robust graph fraud detection noisy labels GNN 2024 2025 (std; 1)
66. "Risk-Gated Heterogeneous Graph Neural Network" fraud (ext; 1)
67. dense subgraph detection pseudo-labels train graph neural network fraud unsupervised to supervised (ext; 1)
68. programmatic labeling functions Snorkel graph neural network anomaly detection weak labels node classification (std; 0)
69. "Knowledge-Guided Fraud Detection Using Semi-supervised Graph Neural Network" (std; 1)
70. rule-based pseudo labels graph neural network fraud detection bootstrapping expert rules label generation transaction graph (ext; 2)
71. message passing gated by co-occurrence of multiple relations between node pair conjunctive multi-relation edge GNN (ext; 0)
72. multiplex graph neural network edge exists in multiple relations weight pair overlap fraud camouflage (std; 1 — PromoGuardian)
73. PromoGuardian promotion abuse fraud multi-relation fused graph neural networks Meituan venue (std; 1)
74. Detecting Fake Reviewer Groups in Dynamic Networks Adaptive Graph Learning Method (std; 1)
75. "PC-GNN" github Liu Ao WWW 2021 label-balanced sampler neighborhood sampler (std; 0)
76. arXiv "Addressing Heterophily in Graph Anomaly Detection" Gao Wang He spectrum (std; 0)
77. STAG low latency low staleness GNN-based services dynamic graphs ICCD 2023 (std; 2)
78. user-attribute bipartite graph GNN fraud shared device IP card popular attribute hub camouflage 2026 arXiv (ext; 2)
79. "InkStream" IPDPS 2025 Wu Li Mitra instantaneous GNN inference dynamic graphs (std; 0 new)

### URLs fetched (✓ read; ✗ failed)
- ✓ https://arxiv.org/pdf/2008.08692
- ✓ https://proceedings.mlr.press/v162/tang22b.html
- ✓ https://proceedings.neurips.cc/paper_files/paper/2023/hash/5eaafd67434a4cfb1cf829722c65f184-Abstract.html
- ✓ https://arxiv.org/pdf/2211.06977
- ✓ https://vldb.org/pvldb/vol17/p4253-jiang.pdf
- ✓ https://www.paperdigest.org/certificate/04ed63f4f38f2d54
- ✓ https://proceedings.neurips.cc/paper_files/paper/2023/hash/5f38404edff6f3f642d6fa5892479c42-Abstract.html
- ✓ https://arxiv.org/pdf/2309.11071
- ✓ https://arxiv.org/abs/2601.12347v1
- ✓ https://arxiv.org/abs/2603.20622
- ✓ https://arxiv.org/html/2505.12112v1
- ✓ https://arxiv.org/pdf/2302.10407
- ✓ https://api.openalex.org/works/doi:10.1145/3485447.3512195
- ✓ https://www.arxiv.org/abs/2512.23777
- ✓ https://www.paperdigest.org/certificate/c4c7e75cbf9ade64
- ✗ https://scholar.hit.edu.cn/en/publications/understanding-theinfluence-ofextremely-high-degree-nodes-ongraph-/ (redirect, not followed)
- ✓ https://ojs.aaai.org/index.php/AAAI/article/view/28785
- ✓ https://ojs.aaai.org/index.php/AAAI/article/download/29593/31000
- ✓ https://arxiv.org/pdf/2104.07886
- ✓ https://arxiv.org/pdf/2205.13084
- ✓ https://arxiv.org/abs/2011.12193v3
- ✓ https://arxiv.org/pdf/2002.12307
- ✓ https://dspace.mit.edu/handle/1721.1/157762
- ✓ https://jshun.csail.mit.edu/FraudGT.pdf
- ✓ https://arxiv.org/abs/2506.02451v1
- ✓ https://cgi.cse.unsw.edu.au/~zhangw/files/2023_KDD_paper.pdf
- ✓ https://opus.lib.uts.edu.au/bitstream/10453/175329/3/KDD_ADS_160_OPUS.pdf
- ✓ https://arxiv.org/abs/2510.13205v1
- ✓ https://mlanthology.org/ecmlpkdd/2021/mathew2021ecmlpkdd-defraudnet
- ✓ https://odr.chalmers.se/items/8ebac935-a21a-44b6-82fd-9524894ac799/full
- ✓ https://huggingface.co/papers/2412.18287
- ✓ https://arxiv.org/pdf/2605.26040
- ✓ https://ar5iv.labs.arxiv.org/html/2210.14360
- ✓ https://arxiv.org/html/2406.11389v1
- ✓ https://arxiv.org/abs/2308.01063v1
- ✓ https://arxiv.org/abs/2601.10193v1
- ✓ https://ai.stanford.edu/~jure/pubs/pinsage-kdd18.pdf
- ✓ https://www.comp.nus.edu.sg/~tulika/IPDPS25.pdf
- ✓ https://arxiv.org/abs/2011.11545v2
- ✓ https://arxiv.org/pdf/2206.01379
- ✓ https://arxiv.org/html/2603.21090
- ✓ https://arxiv.org/abs/2412.00020
- ✓ https://papers.neurips.cc/paper_files/paper/2024/hash/f57de20ab7bb1540bcac55266ebb5401-Abstract-Conference.html
- ✓ https://www.ijcai.org/proceedings/2025/365
- ✓ https://mlanthology.org/iclr/2024/chen2024iclr-consistency
- ✗ https://dl.acm.org/doi/fullHtml/10.1145/3442381.3449989 (site error)
- ✓ https://ar5iv.labs.arxiv.org/html/2106.04513
- ✓ https://arxiv.org/pdf/2601.06800
- ✓ https://arxiv.org/pdf/2604.21093
- ✓ https://proceedings.neurips.cc/paper_files/paper/2022/hash/8f1918f71972789db39ec0d85bb31110-Abstract.html
- ✓ https://papers.neurips.cc/paper_files/paper/2022/hash/d9696563856bd350e4e7ac5e5812f23c-Abstract-Datasets_and_Benchmarks.html
- ✓ https://ojs.aaai.org/index.php/AAAI/article/view/29069
- ✓ https://alexbeutel.com/papers/tkdd_fraud_detection_with_camo.pdf
- ✗ https://koasas.kaist.ac.kr/handle/10203/251592?mode=full (page did not load)
- ✓ https://papers.nips.cc/paper/6703-inductive-representation-learning-on-large-graphs
- ✓ https://neurips.cc/virtual/2019/poster/13964
- ✓ https://arxiv.org/abs/2306.06108v1
- ✓ https://ml.cmu.edu/news/news-archive/2016/cmu-team-receives-best-research-paper-award-at-kdd-2016
- ✗ https://videolectures.net/kdd2016_hooi_bounding_graph (bot wall)
- ✓ https://mail.vldb.org/pvldb/volumes/16/paper/Spade%3A%20A%20Real-Time%20Fraud%20Detection%20Framework%20on%20Evolving%20Graphs
- ✓ https://mail.vldb.org/pvldb/volumes/15/paper/xFraud%3A%20Explainable%20Fraud%20Transaction%20Detection
- ✓ https://arxiv.org/pdf/2011.12193v2
- ✓ https://arxiv.org/pdf/2308.15096
- ✓ https://arxiv.org/html/2610.21314
- ✓ https://proceedings.iclr.cc/paper_files/paper/2025/file/7969d456aede0ce6b36fb47cc64c495c-Paper-Conference.pdf
- ✗ https://arxiv.org/html/2610.27107 (rate-limited, 3 attempts)
- ✓ https://arxiv.org/html/2512.19061v1
- ✓ https://proceedings.mlr.press/v300/cai26b.html
- ✓ https://ir.webis.de/anthology/2022.cikm_conference-2022.326/
- ✓ https://ir.webis.de/anthology/2020.sigirconf_conference-2020.173
- ✓ https://mlanthology.org/iclr/2024/zhuo2024iclr-partitioning
- ✓ https://proceedings.iclr.cc/paper_files/paper/2025/hash/24f7b98aef14fcd68acf3c941af1b59e-Abstract-Conference.html
- ✓ https://ojs.aaai.org/index.php/AAAI/article/view/29067
- ✓ https://mail.vldb.org/pvldb/volumes/17/paper/D3-GNN%3A%20Dynamic%20Distributed%20Dataflow%20for%20Streaming%20Graph%20Neural%20Networks
- ✓ https://papers.cool/arxiv/2610.27107
- ✓ https://www.roboticscenter.ai/research/papers/rgh-gnn-risk-gated-heterogeneous-graph-neural-network-for-financial-fraud-detection-2610
- ✓ https://link.springer.com/article/10.1007/s44564-026-00024-z
- ✗ https://dl.acm.org/doi/pdf/10.1145/3539597.3573022 (site error)
- ✓ https://arxiv.org/pdf/2510.12652
- ✓ https://www.comp.nus.edu.sg/~liangzk/publications/beyond.html
- ✓ https://arxiv.org/html/2603.08332v1
- ✓ https://astro.paperswithcode.com/paper/pick-and-choose-a-gnn-based-imbalanced
- ✓ https://ar5iv.labs.arxiv.org/html/2005.00625
- ✓ https://arxiv.org/html/2603.20622v1
- ✓ https://graphscope.io/blog/tech/2023/08/06/Dynamic-Graph-Sampling-Service-for-Realtime-GNN-Inference-at-Scale.html
- ✓ https://jhc.sjtu.edu.cn/~chen-chen/papers/stag-iccd23.pdf
- ✓ https://arxiv.org/abs/2604.14235
- ✓ https://unpaywall.org/10.1145%2F2939672.2939747

### Gaps and caveats
- Not opened: GHRN, H2-FDetector, ConsisGAD, GDN, and Graph Pre-Training GAD (all UNVERIFIED). PC-GNN's ACM page failed. The full RGH-GNN text was rate-limited, so its gate formula is unknown.
- "A Framework for Detecting Frauds from Extremely Few Labels" (WSDM 2023, ACM DOI 10.1145/3539597.3573022) could not be fetched. It may be relevant to Component 3.
- DBLP and Semantic Scholar APIs were not queried, because their URLs did not appear in search results. Second sources were proceedings pages, arXiv listings, mlanthology, webis anthology, VLDB volume pages and institutional pages.
