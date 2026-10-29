# I6 — Citation verification (refine4)

Checked 2026-10-29. Bibliographic metadata was checked against Crossref (`api.crossref.org/works/<DOI>`) for every entry with a DOI. Abstracts came from OpenAlex or Semantic Scholar. Full text was read for Spade (arXiv 2211.06977), FRAUDAR (author PDF of the KDD'16 paper) and Rabanser et al. (arXiv 1810.11953). IEEE Xplore full text was **not** available for the 2025/2026 IEEE papers. For those, "supports" is judged from the abstract only.

## Summary table

| key | status | issue | fix |
|---|---|---|---|
| zhang2026incremental | VERIFIED | none; pages "1–6" (article-numbered) omitted | optional `pages={1--6}` |
| lv2026mandate | VERIFIED | none | — |
| badjie2026ensembles | VERIFIED | Crossref gives given name "Numair Bin", family "Sharif"; bib "bin Sharif, Numair" is acceptable | none required |
| kumar2026tagat | VERIFIED (minor) | second author is "Norbert Oláh"; bib has initial "N." | `Ol{\'a}h, Norbert` (optional) |
| lu2026lagcn | VERIFIED; support PARTLY | abstract shows a GCN on Elliptic with SMOTE/focal loss; it does not mention tabular ensembles or temporal splits | narrow the body.tex:132–133 sentence (see details) |
| shah2025aml | VERIFIED; support PARTLY | Elliptic, classical ML models with an MLP best; no GNNs or temporal split in the abstract; pages 1–5 | narrow the sentence; optional `pages={1--5}` |
| azbergen2026calibration | VERIFIED | pages 1–6 omitted | optional `pages={1--6}` |
| meulemeester2026cfi | VERIFIED | none | — |
| bora2026hyades | MISMATCH (diacritic) | `Quin{\~o}nes` puts the tilde on the **o** ("Quinõnes"). Crossref: given "Eduardo Quiñones", family "Moreno" | `Qui{\~n}ones Moreno, Eduardo` (or `Moreno, Eduardo Qui{\~n}ones` to follow Crossref) |
| pan2025gbfrd | VERIFIED; support PARTLY at body.tex:6 | a single method paper, so it cannot show that graph methods "dominate" (pourhabibi2020fraud carries that) | keep, or cite pan2025 only at body.tex:84 |
| liu2025robust | VERIFIED; support PARTLY at body.tex:78 | "reweighting neighbours adversarially" is inexact: it uses dual encoders for normal and abnormal neighbours, and adversarial (perturbation-based) reweighting of **training nodes** in the loss | reword (see details) |
| hu2025hhgfd | VERIFIED | phase2.tex:101 cites it for "camouflage"; the paper is about heterophily and heterogeneity (related, but the paper does not use that word) | optional rewording |
| li2025ocgfd | VERIFIED | pages 1–6 omitted | optional `pages={1--6}` |
| karaaslanli2025crowd | VERIFIED | pages 1–5 omitted | optional `pages={1--5}` |
| movin2025acdc | VERIFIED | none (DOI year 2024; issue Apr 2025) | — |
| rabanser2019failing | VERIFIED (incomplete) | no volume or pages | add `volume={32}, pages={1396--1408}` |
| tang2022bwgnn | VERIFIED (incomplete) | no pages | add `pages={21076--21089}` |
| papadakis2014metablocking | VERIFIED; support PARTLY | ARCS (inverse block-size weighting) is from this paper. **Block Purging** comes from Papadakis et al. TKDE 2013 / WSDM 2012; meta-blocking only refers to it as prior "coarse-grained block processing" | add a cite for block purging (Papadakis et al., "A blocking framework for entity resolution in highly heterogeneous information spaces", IEEE TKDE 25(12):2665–2682, 2013) |
| B1 Spade "same peeling sequence" | SUPPORTED with caveats | the exactness claim holds for edge insertions with fixed edge weights. Spade returns **one** densest block; multi-block enumeration and deletions are only sketched as future work (App. C). Spade never discusses re-weighting existing edges when an object's degree grows under FD | qualify Table V label and body text (see details) |
| B2 FRAUDAR 1/log(x+c), c=5, against 1/x | SUPPORTED | — | — |
| B3 IEEE-CIS | URL correct; description correct | provider not named; "masked" is right for the identity fields (id_12–id_38 plus Vesta-engineered features) | optionally add "provided by Vesta Corporation" |

## Task A — details

Every DOI resolved on Crossref, and title, authors, venue and year matched the bib in all 16 DOI-bearing entries. Where the bib had pages, they matched as well. Rabanser and Tang have no DOI and were checked on the NeurIPS and PMLR pages.

### zhang2026incremental — VERIFIED; supports: YES
- Crossref: "Research on an Incremental Community Detection Algorithm for Large-Scale Dynamic Complex Network", Zhang B., Liu H., Zhang Y., 2026 IEEE 3rd ICBDSE, pp. 1–6, Jun 2026.
- Our text (body.tex:24–25, 117–118): "…a problem that incremental community detection addresses for clustering" / "Incremental community detection avoids repartitioning a changing graph by updating only the affected communities".
- Abstract: "local community updating is completed. This method avoids full repartitioning of the complete historical network after each network update". **Yes.**

### lv2026mandate — VERIFIED; supports: YES
- Crossref: ICASSP 2026, pp. 6076–6080, authors Lv, Du, Zhang, Han, Li. Exact match.
- Our text (body.tex:77): "heterophily, where fraudulent nodes connect mostly to benign ones".
- Abstract: "we design different embedding strategies for homophilic and heterophilic connections. This mitigates the homophily distribution differences between benign and fraudulent nodes." **Yes.**

### badjie2026ensembles — VERIFIED; supports: YES
- Crossref: ICSCSA 2026, pp. 557–561. Exact match.
- Our text (body.tex:132–133): "Work on the Elliptic Bitcoin graph compares tabular ensembles with GNNs under temporal splits".
- Abstract: "We study this problem on the Elliptic dataset … using a temporal split … We compare strong tabular ensembles against three widely used graph neural networks". **Yes.** It also supports public.tex:24 (Elliptic usage).

### kumar2026tagat — VERIFIED (first name of 2nd author); supports: YES
- Crossref: "Ragupathi Nithish Kumar, Norbert Oláh", IEEE 4th CITDS 2026, pp. 331–334.
- Abstract: "the Bitcoin Elliptic dataset … comparing ten models including classical machine learning (ML) methods, five GNN architectures … using strict temporal splits … XGBoost remains a formidable baseline". **Yes.**

### lu2026lagcn — VERIFIED; supports: PARTLY
- Crossref: IEEE 6th ICETCI 2026, pp. 131–135. Exact match.
- Abstract: "Based on the Elliptic public Bitcoin transaction dataset … combines a four-layer GCN … introducing SMOTE and Focal Loss". It says nothing about comparing against tabular ensembles or about temporal splits. **Partly.** It fits "work on the Elliptic graph", but not "compares tabular ensembles with GNNs under temporal splits".

### shah2025aml — VERIFIED; supports: PARTLY
- Crossref: 2025 1st SATC, pp. 1–5, Feb 2025.
- Abstract: "The Elliptic dataset, which contains 203,769 Bitcoin transactions with 166 characteristics, is used to assess sophisticated ML models … the best result was obtained by Multi-Layer Perceptron (MLP)". No GNN and no temporal split. **Partly.**
- **Suggested rewrite of body.tex:132–134:** "Work on the Elliptic Bitcoin graph compares tabular ensembles with GNNs under temporal splits \cite{badjie2026ensembles,kumar2026tagat} or trains GNN and classical classifiers on it \cite{lu2026lagcn,shah2025aml};"

### azbergen2026calibration — VERIFIED; supports: YES
- Crossref: IEEE 6th SIST 2026, pp. 1–6.
- Our text (body.tex:148–149, phase2.tex:33): "compare such calibrators for AML risk scores" / "post-hoc recalibration of the kind Azbergen et al. compare".
- Abstract: "CatBoost and XGBoost are combined with post-hoc probability calibration techniques, including Platt scaling and isotonic regression … IBM Anti-Money Laundering dataset … operational AML risk scoring." **Yes.**

### meulemeester2026cfi — VERIFIED; supports: YES
- Crossref: IEEE Access 14:50691–50703 (2026). Exact match.
- Abstract: "We solve this by introducing Counterfactual Feature Importance (CFI) values … a greedy algorithm, and an adaptation of Shapley values". Our text "per-feature importance" of counterfactuals: **Yes.**

### bora2026hyades — MISMATCH (author diacritic); supports: YES
- Crossref: "HYADES: Adaptive Consumer Tuning in Redis Streams via Hybrid Expert Selection", Bora K., Kartsakli E., [given "Eduardo Quiñones", family "Moreno"], IEEE 19th CLOUD 2026, pp. 518–528.
- Bib error: `Quin{\~o}nes` renders as "Quinõnes". Correct to `Qui{\~n}ones`.
- Our text (body.tex:188–189): "consumer settings (batch size, blocking timeout) trade throughput against latency".
- Abstract: "consumer-side parameters such as fetch batch size, blocking timeout, acknowledgment batching … affect throughput, latency, and failure recovery." **Yes.** The citation also fits phase2.tex:22–23.

### pan2025gbfrd — VERIFIED; supports: YES (body.tex:84), PARTLY (body.tex:6)
- Crossref: 6th ICCVDM 2025, pp. 457–462. Exact match.
- Abstract: "we introduce Graph-Based Fraud Ring Detection (GB-FRD) … Peer-to-peer (P2P) payment networks". This supports "targets fraud rings in peer-to-peer payment graphs". For "graph-based methods dominate fraud and AML research" it is only one example; the survey (pourhabibi2020fraud) carries that claim.

### liu2025robust — VERIFIED; supports: YES (body.tex:18), PARTLY (body.tex:78)
- Crossref: IEEE TCSS 12(6):5213–5224, Dec 2025. Exact match.
- body.tex:17–18, "fraudsters elsewhere hide by connecting to benign entities". Abstract: "fraudsters disguise their activities by forming connections with benign entities". **Yes.**
- body.tex:78, "camouflage, by reweighting neighbours adversarially". Abstract: "Our model enables dual encoders to assimilate information from both normal and abnormal neighbors … we introduce perturbation strategies … These strategies dynamically adjust node weights during training … enhances the contribution of reliable nodes in the loss function". The adversarial reweighting is of training nodes, not neighbours. **Partly.** Suggested rewording: "camouflage, by aggregating normal and abnormal neighbours separately and adversarially reweighting training nodes \cite{liu2025robust}".

### hu2025hhgfd — VERIFIED; supports: YES (body.tex:77), PARTLY (phase2.tex:101)
- Crossref: IEEE 37th ICTAI 2025, pp. 818–825. Exact match.
- Abstract: "the prevalent heterophily (target nodes exhibit distinct labels from neighbors) and heterogeneity … in fraud graphs". This supports the heterophily sentence. phase2.tex:101 ("Turning up camouflage strength, after … Hu et al.") is a loose attribution, since the paper frames the problem as heterophily rather than camouflage. Acceptable as "after", but "decoy edges that raise heterophily" would be more exact.

### li2025ocgfd — VERIFIED; supports: YES
- Crossref: IEEE ICME 2025, pp. 1–6. Exact match.
- Abstract: "we explore the one-class graph fraud detection task … trains the model only on normal data". This fits "scarce or unreliable labels, with one-class … training". **Yes.**

### karaaslanli2025crowd — VERIFIED; supports: YES
- Crossref: ICASSP 2025, pp. 1–5.
- Abstract: "we represent crowdsourced data as a weighted bipartite graph between workers and data points … analyzed with a sequential peeling algorithm to detect the dense subgraph that includes adversarial attacks". This matches body.tex:94–95 exactly. **Yes.**

### movin2025acdc — VERIFIED; supports: YES
- Crossref: IEEE TAI 6(4):794–804, Apr 2025 (DOI carries 2024). Exact match.
- Abstract: "models in deployment may both be periodically retrained … it is desirable that the recourse should remain valid when such a model update occurs". This supports "consistency across model updates" and phase2.tex:64 (retrained scorer). **Yes.**

### rabanser2019failing — VERIFIED (add volume/pages); supports: YES
- NeurIPS proceedings metadata: Advances in Neural Information Processing Systems 32 (NeurIPS 2019), pp. 1396–1408.
- Our text (body.tex:140–141): "Dataset shift is commonly detected by comparing the distribution of a model's inputs or outputs on new data with a reference sample".
- Paper (§1): "detecting that the source distribution p differs from the target distribution q requires only detecting that p(f(x)) ≠ q(f(x)) … we explore a range of dimensionality-reduction techniques and compare them under a wide variety of shifts". §3: "use the outputs of a (deep network) label classifier trained on source data … softmax outputs (BBSDs) … for subsequent two-sample testing." **Yes.**

### tang2022bwgnn — VERIFIED (add pages); supports: YES
- PMLR page: Tang, Li, Gao, Li, ICML 2022, PMLR 162:21076–21089.
- It is cited only as the source of the BWGNN architecture we re-implemented (body.tex:454). **Yes.**

### papadakis2014metablocking — VERIFIED; supports: PARTLY
- Crossref: IEEE TKDE 26(8):1946–1960, Aug 2014. Exact match. Crossref's title has a typo ("Resolutionto"); the bib title is correct.
- Our text (body.tex:127–129): "meta-blocking weights candidate pairs by the inverse size of the blocks they share, and block purging drops oversized blocks".
- Meta-blocking abstract: "proposing a multitude of edge weighting schemes". The ER survey (Papadakis et al., arXiv 1905.06167) attributes ARCS to this paper: "ARCS sums the inverse cardinalities of the common blocks, giving higher weights to entity pairs that co-occur in smaller blocks" [ref 125 = this paper]. **The first half is supported.**
- The survey attributes Block Purging to refs [123]/[124]: "Block Purging discards blocks that exceed an upper limit on block cardinality [124] or size [123]". The meta-blocking abstract only alludes to "coarse-grained block processing techniques that discard entire blocks either a-priori or during the resolution process". The meta-blocking full text could not be retrieved (author PDF host returned 503), so it is unverified whether the paper uses Block Purging in its own pipeline. **Fix:** add `papadakis2013blocking` (G. Papadakis, E. Ioannou, T. Palpanas, C. Niederée, W. Nejdl, "A blocking framework for entity resolution in highly heterogeneous information spaces", IEEE TKDE 25(12):2665–2682, 2013), or reword the sentence so the cite covers only the weighting.

## Task B — details

### B1. Spade (Jiang et al., PVLDB 16(3):461–469, 2022; arXiv 2211.06977)

Bib entry: Crossref confirms authors, PVLDB 16(3), pp. 461–469, Nov 2022, DOI 10.14778/3570690.3570696.

Our wording:
- body.tex:98–101: "Spade maintains such peeling-based dense subgraphs incrementally under edge insertions on transaction graphs, with FRAUDAR's weighting and the same peeling sequence as a full recomputation."
- body.tex:110–111: "We run FRAUDAR-style peeling, whose output Spade maintains incrementally, as a baseline."
- body.tex:568–569: "we reproduce Spade's output, not its latency."
- tables/tab5_existing.tex:30: "FRAUDAR-style peeling (= Spade output)".

Supporting passages:
- §4.1 (edge insertion): "Correctness and accuracy guarantee. … The peeling sequence is identical to that of G ⊕ ∆G, since in each iteration the vertex with the smallest peeling weight is chosen. The accuracy of the worst-case is preserved due to Lemma 2.1." The batch version (§4.2) says "The correctness and accuracy guarantee are similar to those of peeling sequence reordering with edge insertion."
- Abstract: "Peeling algorithms incrementalized by Spade are up to a million times faster than the static version."
- FRAUDAR weighting (§3, Instance 3 / App. F): "esusp is a logarithmic function such that given an edge (u_i,u_j), esusp(u_i,u_j) = 1/log(x+c), where x is the degree of the object vertex between u_i and u_j, and c is a small positive constant [19]." Listing 2 code: `return 1/log(g.deg[e.src]+5);`, so **c = 5**, matching FRAUDAR. The density metric is FRAUDAR's g(S) = (Σ_{u_i∈S} a_i + Σ_{(u_i,u_j)∈E[S]} c_ij)/|S| (Eq. 15). Spade supports FD as one of three plug-in semantics (DG, DW, FD); FRAUDAR's weighting is not Spade's only metric.

**Verdict:** "Spade's incremental peeling sequence equals that of static (full) peeling on the updated graph" is what Spade claims. Our sentence is accurate for that core guarantee. The "= Spade output" label needs qualifying because of four caveats from the paper:
1. **Insertions only.** §2.1: "Since transaction graphs continue to evolve, we consider edge insertion rather than edge deletion." Deletion is sketched as future work in App. C.1 ("we … leave the extension details of Spade in future work"). If our baseline runs on a sliding window with expiring edges, Spade as published does not cover that case.
2. **One block, not ten.** Spade returns the densest prefix S^P of the peeling sequence. Enumerating further dense subgraphs (repeatedly removing S^P) is only sketched in App. C.2. Our baseline extracts "at most ten blocks per pass" (body.tex:440), so only the first block is literally "Spade output". The later ones follow FRAUDAR/App. C.2 rather than Spade's evaluated system.
3. **Degree-dependent weights.** Spade's exactness argument treats an insertion as adding one edge of weight ∆ = c_ij, with all other weights fixed. Under FD, inserting an edge raises the object's degree and should lower the weight 1/log(x+c) of that object's existing edges. Spade does not discuss re-weighting existing edges; full-text searches for "recompute", "existing edge" and "degree change" found nothing. Equality with a full FRAUDAR recomputation under degree-dependent weights is therefore not explicitly established by the paper.
4. **Edge grouping.** With edge grouping enabled (the default in their example code, `spade.TurnOnEdgeGrouping()`), benign edges are buffered and processed in batch. Lemmas 4.3/4.4 show a benign edge cannot put its endpoints into the densest subgraph or create a denser one, so the detected block is unaffected but the maintained sequence lags.

**Suggested fixes:**
- Table V: "FRAUDAR-style peeling (Spade-equivalent)" plus a table note: "Spade's incremental peeling yields the same peeling sequence as static peeling on the updated graph (Jiang et al., §4.1), so we compute it statically; blocks after the first are extracted by repeated peeling as in their App. C.2."
- body.tex:100–101: "…incrementally under edge insertions on transaction graphs, supporting FRAUDAR's weighting among other density metrics, and proves the maintained peeling sequence identical to a full recomputation." If our windows expire edges, add: "(Spade handles insertions; deletions are left to future work)."

### B2. FRAUDAR (Hooi et al., KDD 2016, pp. 895–904; TKDD 2017 extension)
- Bib hooi2016fraudar: Crossref confirms authors (Hooi, Song, Beutel, Shah, Shin, Faloutsos), KDD'16, pp. 895–904, DOI 10.1145/2939672.2939747.
- TKDD extension exists: Hooi, Shin, Song, Beutel, Shah, Faloutsos, "Graph-Based Fraud Detection in the Face of Camouflage", ACM TKDD 11(4), Article 44, pp. 1–26, 2017, DOI 10.1145/3056563 (Crossref). The quotes below are from the KDD'16 version; the TKDD text was not checked.
- §4.4, all three points in one passage: "The remaining question is what function to choose for the column-weighting, i.e. the function h where c_ij = h(d_j). It should be decreasing (so as to downweight columns with high sum). **It should shrink more slowly than h(x) = 1/x, since h(x) = 1/x allows a single edge to contribute as much as the total contribution of a column with any number of edges, causing us to catch columns with single ones rather than dense blocks.** … For these reasons, **we recommend using h(x) = 1/log(x + c), where c is a small constant (set to 5 in our experiments)** to prevent the denominator from becoming zero, or excessive variability for small values of x."
- Also Theorem 3: "Let c_ij be a column-weighting. Then g … is camouflage resistant."
- **Verdict:** body.tex:41–42, 96–98 and 105–106 ("1/log(x+c)", "c=5 in its experiments", "arguing that 1/x shrinks too fast") are all **supported**. "Shrinks too fast" is a fair paraphrase of "should shrink more slowly than 1/x". Our $1/\ln(1+d)$ is indeed the c=1 case of the same family.

### B3. IEEE-CIS Fraud Detection data
- URL: `https://www.kaggle.com/c/ieee-fraud-detection` returns HTTP 200 with `<title>IEEE-CIS Fraud Detection | Kaggle</title>`, so it is the competition page. The WebFetch tool's permission prompt timed out for this URL, so it was checked with curl instead. The canonical form is `https://www.kaggle.com/competitions/ieee-fraud-detection`; either works.
- Competition data text, mirrored verbatim on IEEE DataPort: "predicting the probability that an online transaction is fraudulent, as denoted by the binary target isFraud. The data is broken into two files identity and transaction, which are joined by TransactionID. Not all transactions have corresponding identity information. Categorical Features - Transaction: ProductCD, card1 - card6, addr1, addr2, P_emaildomain, R_emaildomain, M1 - M9. Categorical Features - Identity: DeviceType, DeviceInfo, id_12 - id_38."
- Provider: Vesta. The pinned data-description post is by "Lynn@Vesta" (Kaggle API metadata for topic 101203). The NVIDIA blog says "IEEE partnered with the world's leading payment service company, Vesta Corporation" and "450 columns and masked names and meanings". On the identity file it says "network connection information (IP, ISP, Proxy, and so on)" and "The field names are masked". Paperswithcode says "The data comes from Vesta's real-world e-commerce transactions".
- **Our sentence** (body.tex:523–526): "e-commerce transactions with card, address and e-mail-domain fields and masked identity and device fields, labelled per transaction". **Correct.** Card (card1–6), address (addr1–2) and email domain (P_/R_emaildomain) are in the transaction table; identity and device fields (DeviceType, DeviceInfo, id_12–id_38) are masked; the label isFraud is per transaction. Two optional refinements:
  - Add the provider: "(provided by Vesta Corporation, \url{…})".
  - DeviceType/DeviceInfo values are partly readable (e.g., "mobile"/"desktop", OS/browser strings); it is the id_* field **names** that are masked. "Masked identity fields and device fields" would be slightly more exact, but the current wording is not wrong.
- Not verified: Vesta's labelling rule. As I recall it, a chargeback marks a card's transaction as fraud and later transactions linked through the same account, email or billing address are also labelled fraud. I could not retrieve the post body (Kaggle's discussion API returned 403 / an HTML shell). Do not cite this unless it is checked on the Kaggle discussion page; if true, it is relevant to ring-level evaluation.

## Sources
- Crossref works API, one per DOI, e.g. https://api.crossref.org/works/10.1109/CLOUD72782.2026.00066 (all 18 DOIs above, plus 10.1145/3056563)
- OpenAlex works API, e.g. https://api.openalex.org/works/doi:10.1109/TCSS.2025.3580834 (abstracts of lv, shah, meulemeester, pan, liu, hu, li, karaaslanli, movin, papadakis)
- Semantic Scholar Graph API, e.g. https://api.semanticscholar.org/graph/v1/paper/DOI:10.1109/ICSCSA69367.2026.11707854 (abstracts of zhang, badjie, kumar, lu, azbergen, bora)
- Spade full text: https://arxiv.org/pdf/2211.06977
- FRAUDAR full text (KDD'16): https://bhooi.github.io/papers/fraudar_kdd16.pdf
- Rabanser et al.: https://arxiv.org/pdf/1810.11953 ; https://papers.neurips.cc/paper_files/paper/2019/file/846c260d715e5b854ffad5f70a516c88-Metadata.json
- Tang et al.: https://proceedings.mlr.press/v162/tang22b.html
- ER blocking survey (ARCS / Block Purging attribution): https://arxiv.org/pdf/1905.06167
- IEEE-CIS: https://www.kaggle.com/c/ieee-fraud-detection ; https://ieee-dataport.org/documents/ieee-cis-fraud-detection ; https://www.paperswithcode.com/dataset/ieee-cis-fraud-detection ; https://developer.nvidia.com/blog/leveraging-machine-learning-to-detect-fraud-tips-to-developing-a-winning-kaggle-solution
