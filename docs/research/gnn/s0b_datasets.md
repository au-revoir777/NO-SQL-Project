# Stage 0B: Public dataset search and audit for EvidGNN

Date of search and downloads: 2026-10-27 (UTC). Machine: 2 cores (shared), about 7 GB RAM, no GPU. All downloaded data is in the session scratchpad under `/tmp/claude-0/-home-claude/5e05fd61-12b1-5efc-aab4-f0b57c7050a4/scratchpad/datasets/`, not in this repo. All files were read with `python3 -I`. No downloaded code was executed. Every number marked **[computed]** came from the downloaded files using the audit scripts in Section 4.4. Every number marked **[paper]** or **[README]** is quoted from the cited source. "Not computed" means the data was not obtained.

---

## 1. Summary

- **Shortlist:** (1) **Elliptic++ actors**, GO: real data, and co-input transactions act as hubs with 109 groups over 250 members. (2) **AMLworld HI-Small**, GO: synthetic; entity co-ownership hubs of up to 7,820 accounts, minute timestamps and transfers. (3) **YelpChi**, GO for the gate and label-efficiency parts only, because it has no timestamps.
- **Downloads that worked here:** GitHub (git clone), data.dgl.ai, Google Drive (`drive.usercontent.google.com`), Hugging Face, and anonymous Kaggle **dataset** downloads.
- **Blocked or gated:** IEEE-CIS needs a Kaggle login and acceptance of the competition rules (HTTP 401). DGraph-Fin needs registration, and `dgraph.xinye.com` returned CONNECT 502. The `api.github.com` API was not enabled for this session (403).
- **Excluded:** T-Finance (edges are transaction records, not shared attributes; no timestamps), T-Social and DGraph-Fin (millions of nodes, no documented subsample), Elliptic (payment flow only), BAF (no relations between instances), and TravelFraudBench (synthetic; its largest group has 27 members; shared IP and card groups contain only fraud users).
- **Pending, decided locally:** IEEE-CIS is the best semantic match (card, address, email and device fields). Fetch it locally and run the audit in Section 4. If its groups pass the 250-member test, it can replace YelpChi as #3.

---

## 2. Audit cards

### How the hub audit is defined

- **Clique-decomposable relation** (a released user–user relation in which every connected component is a complete clique, as checked): group = connected component. "Share of edges" is the share of the relation's edges that lie inside groups with more than T members.
- **Bipartite or constructible attribute** (user–attribute memberships such as entity, transaction or payee): group = the set of users holding one attribute value. I report two shares: the share of memberships in groups with more than T members, and the share of projected user–user pairs (k(k−1)/2 per group) that come from those groups.
- **Projection that is not clique-decomposable** (Amazon, T-Finance and the other GADBench graphs): the groups cannot be recovered. I report node-degree quantiles and the share of edges incident to nodes of degree above T, as a proxy.
- **Label rate:** the positive rate among members of hub-sized groups (more than T) versus members of smaller shared groups (2 to T members). T is 27 and 250.

---

### 2.1 YelpChi (CARE-GNN / DGL `FraudYelpDataset`)

**1. Source.** CARE-GNN, Dou et al., CIKM 2020, arXiv [2008.08692](https://arxiv.org/abs/2008.08692). The file is `data/YelpChi.zip` in https://github.com/YingtongDou/CARE-GNN at commit `a64ff7523e187a24251f7ca88435d2c9d8f7dcd9`. It is byte-identical to https://data.dgl.ai/dataset/FraudYelp.zip (same SHA-256). Format: MATLAB v5 `.mat` with the keys `homo`, `net_rur`, `net_rtr`, `net_rsr`, `features` (45,954×32 sparse) and `label`. Size: 17,980,652 B zipped and 207,676,376 B unzipped. Licence: the repo code is Apache-2.0, and no licence is stated for the data. No login is needed. Download: `git clone` or `curl -LO https://data.dgl.ai/dataset/FraudYelp.zip`.

**2. Fetched here:** yes, by both routes.

**3. Structure** [computed; matches paper Table 2]:
- 45,954 review nodes, one node type.
- Labels: 6,677 fraud (14.53%), and every node is labelled.
- Undirected edges: R-U-R 49,315, R-T-R 573,616, R-S-R 3,402,743, homo 3,846,979.
- Relation definitions [paper]:
  - R-U-R: "reviews posted by the same user".
  - R-T-R: "two reviews under the same product posted in the same month".
  - R-S-R: "reviews under the same product with the same star rating".
- Splits: no split is stored in the file.
  - CARE-GNN `train.py`: stratified 40/60, `random_state=2`.
  - PC-GNN: `train_ratio` argument, `random_state=2`.
  - DGL: 70/10/20 with seed 717 [DGL docs].
  - GADBench: 20 stored masks.

**4. Hub audit** [computed with `audit_mat.py`]:

| Relation | Semantics | Clique-decomposable? | Group size p50 / p90 / p99 / max | Groups >27 (edge share) | Groups >250 (edge share) | Fraud rate: >27 members vs others | Fraud rate: >250 members vs others |
|---|---|---|---|---|---|---|---|
| R-U-R | genuine shared attribute (same user) | yes, 100% of 7,308 components | 2 / 6 / 13 / 47 | 3 (4.8%) | 0 | 0.000 vs 0.051 | n/a |
| R-S-R | shared attribute (product × star) | yes, 100% of 763 components | 29 / 178 / 292 / 466 | 392 (99.1%) | **22 (28.4%)** | 0.139 vs 0.206 | 0.150 vs 0.145 |
| R-T-R | stated as product × month | **no**: 35.7% of components are cliques; median component density 0.57, minimum 0.198 | components: 8 / 105 / 186 / 331 (upper bounds) | 465 (97.6%) | 2 (3.9%) | 0.148 vs 0.123 | 0.073 vs 0.146 |
| homo | union of the three | no | node degree 168 / 290 / 466 / 501 | — | — | — | — |

- R-U-R has 22,123 isolated nodes, and its non-isolated nodes have a fraud rate of only 5.1% against 14.5% overall. Fraud reviews mostly come from single-review users.
- **Anomaly:** the stored R-T-R relation is not a disjoint union of (product, month) cliques, which contradicts the paper's definition. Treat R-T-R groups as unknown.

**5. Fit for each component:**
- **Gate, partial.** There are three relations but no transfers. Only **5.0%** of R-S-R pairs inside groups over 250 also have R-T-R or R-U-R evidence (6.9% in groups of 27 or fewer). Among the 5.0% that do, the share of pairs where both nodes are fraud is 0.048, against 0.037 for pairs without second evidence. [computed, `gate_evidence.py`]
- **Incremental inference: no.** The released features are 32 behavioural and text features with no time column, so any event order would be synthetic.
- **Labels: yes**, fully labelled.

**6. Preprocessing and verdict.** Preprocessing: connected components on R-U-R and R-S-R give exact group lists. Measured peak memory of the audit: 724 MB. **GO** for components 1 and 3 and for comparability with CARE-GNN and PC-GNN. **NO-GO** for component 2 unless the event order is labelled as simulated.

---

### 2.2 Amazon (CARE-GNN / DGL `FraudAmazonDataset`)

**1. Source.** Same paper as YelpChi. The file is `data/Amazon.zip` at CARE-GNN commit `a64ff75…`. It is byte-identical to https://data.dgl.ai/dataset/FraudAmazon.zip. Size: 26,122,297 B zipped and 222,634,416 B unzipped. Licence: as for YelpChi.

**2. Fetched here:** yes.

**3. Structure** [computed]:
- 11,944 user nodes; 821 positive.
- The first 3,305 nodes are stored with label 0 but are treated as unlabelled by the CARE-GNN and PC-GNN code (`index = range(3305, …)`). The rate among the remaining nodes is 821/8,639 = 9.50%, which matches the paper's 9.5%.
- Undirected edges: U-P-U 175,608, U-S-U 3,566,479, U-V-U 1,036,737, homo 4,398,392 (all match the paper).
- Relation definitions [paper]:
  - U-P-U: "users reviewing at least one same product".
  - U-S-U: "at least one same star rating within one week".
  - U-V-U: "top 5% mutual review text similarities (TF-IDF)".

**4. Hub audit** [computed; node-degree proxy, because none of the relations is clique-decomposable]:

| Relation | Semantics | Node degree p50 / p90 / p99 / max | Degree >27: nodes (edge share) | Degree >250: nodes (edge share) | Positive rate: degree >250 vs ≤250 |
|---|---|---|---|---|---|
| U-P-U | shared attribute (co-review projection, overlapping cliques; groups not recoverable) | 8 / 63 / 418 / 511 | 2,021 (88.9%) | 446 (54.9%) | 0.173 vs 0.063 |
| U-S-U | co-occurrence in a time window (weak attribute) | 268 / 1,692 / 3,754 / 6,311 | 10,878 (≈100%) | 6,151 (97.6%) | 0.027 vs 0.114 |
| U-V-U | **similarity**, so no hub semantics | 92 / 413 / 1,411 / 6,477 | 9,034 (99.5%) | 2,071 (85.3%) | 0.011 vs 0.079 |

These rates count the 3,305 unlabelled nodes as negatives, so they are biased low.

**5. Fit.** Gate: three relations, but the product groups cannot be recovered and one relation is a similarity. Incremental inference: no timestamps. Labels: yes.

**6. Verdict.** Memory is under 1 GB. **NO-GO as a primary dataset.** It is optional as a secondary benchmark for comparability only.

---

### 2.3 T-Finance (BWGNN / GADBench)

**1. Source.** BWGNN, Tang et al., ICML 2022 ([PMLR v162](https://proceedings.mlr.press/v162/tang22b.html)). The data is on Google Drive (folder `1PpNwvZx_YRSCDiHaBUmRIS3x1rZR7fMr`, linked from https://github.com/squareRoot3/Rethinking-Anomaly-Detection at commit `de0631f…`, which has no licence file). I used the GADBench bundle instead, which is Drive file `1txzXrzwBBAOEATXmfKzMUUKaXh6PJeR1` (`datasets.zip`, 757,193,110 B). The `tfinance` file in it is 1,023,882,459 B in DGL binary format. No login is needed.

**2. Fetched here:** yes, through the GADBench zip. I parsed the DGL binary without DGL by scanning its NDArray headers (`dgl_scan.py`).

**3. Structure:**
- [computed] 39,357 nodes. 21,222,543 undirected edges, stored as 42,484,443 directed edges that include 39,357 self-loops. 1,803 anomalies (4.58%). 10 features. 20 split masks: trial 0 has 15,742 training nodes, and semi-supervised trial 10 has 100.
- [paper] "The edges in the graph represent two accounts that have transaction records."
- [paper] Labels come from human experts and cover fraud, money laundering and online gambling.

**4. Hub audit** [computed; node-degree proxy]:
- Node degree p50 / p90 / p99 / max: 265 / 5,614 / 6,311 / 7,723.
- Degree >27: 35,500 nodes, 99.98% of edges incident.
- Degree >250: 20,362 nodes, 98.7% of edges incident. Positive rate 5.99% vs 3.07%.
- Sampled local clustering mean: 0.34.
- Semantics: an interaction (transaction-record) relation, **not a shared attribute**. Only one relation, with no edge attributes.

**5. Fit.** Gate: one kind of evidence only. Incremental inference: no timestamps. Labels: yes.

**6. Verdict.** Measured peak memory: 1.76 GB. **NO-GO.**

### 2.4 T-Social

- **Source:** same Drive folder or GADBench zip (`tsocial`, 5,580,604,102 B uncompressed; not extracted).
- [paper] 5,781,065 nodes and 73,105,508 edges; 3.01% anomalies. "two nodes are connected if they maintain the friend relationship for more than three months."
- **Hub audit:** not computed (not extracted).
- **Verdict: NO-GO.** It has millions of nodes and no documented subsample, the edges are friendship rather than shared attributes, and there are no timestamps.

### 2.5 DGraph-Fin

- **Source:** Huang et al., NeurIPS 2022 D&B, arXiv [2207.03579](https://arxiv.org/pdf/2207.03579).
- **Access:** https://dgraph.xinye.com/ requires registration (name and email) and agreement to the user licence at https://dgraph.xinye.com/clause, which I did not open. The paper says the licence is non-commercial.
- **Code:** https://github.com/DGraphXinye/DGraphFin_baseline (HEAD `b357023af848b6cd1f976a9ba600ec42a1ec85cf`, checked with `git ls-remote`; code only).
- **Fetched here:** no. `dgraph.xinye.com` returned CONNECT 502. PyG's `DGraphFin` loader exists, but its documentation gives no download URL.
- **Structure** [paper]:
  - 3,700,550 nodes and 4,300,999 directed edges. An edge means that a user lists another user as an emergency contact.
  - Edges carry time information as time gaps only.
  - Labels: 15,509 fraud, 1,210,092 normal and 2,474,949 background nodes.
  - 17 features; fixed random 70/15/15 split.
- **Hub audit:** not computed (data not obtained). One constructible shared attribute exists: users who list the same emergency contact form a group, so the contact's in-degree is the group size.
- **Verdict: NO-GO.** It has millions of nodes, no documented subsample and gated access.

### 2.6 Elliptic

**1. Source.** Weber et al. 2019, arXiv [1908.02591](https://arxiv.org/pdf/1908.02591). Kaggle `ellipticco/elliptic-data-set`, version 1, licence CC BY-NC-ND 4.0 [Kaggle API]. Anonymous Kaggle API bundle download: `archive.zip`, 153,218,318 B.

**2. Fetched here:** yes. Per-file downloads returned 404 HTML pages; the bundle worked.

**3. Structure:**
- [computed; matches paper] 203,769 transactions and 234,355 directed payment-flow edges. 49 time steps, about two weeks apart [paper]. 4,545 illicit, 42,019 licit and 157,205 unknown. 166 features.
- Splits: train on steps 1–34 and test on 35–49 [paper]. GADBench uses ≤25 / 26–34 / >34 (its `preprocess.ipynb`).

**4. Hub audit** [computed]:
- Undirected degree p50 / p90 / p99 / max: 2 / 3 / 13 / 473.
- Degree >27: 613 nodes, 15.7% of edges. Degree >250: 3 nodes, 0.45% of edges.
- Illicit rate among labelled nodes: 5.3% for degree >27, against 9.8% otherwise.
- Payment flow: **no shared-attribute relation.**

**5–6. Fit and verdict.** It has time steps and labels but no second kind of evidence. **NO-GO.** Its transaction time steps are reused below to order Elliptic++ events.

---

### 2.7 Elliptic++ (actors and wallet addresses), shortlist #1

**1. Source.**
- Paper: Elmougy & Liu, KDD 2023, DOI [10.1145/3580305.3599803](https://doi.org/10.1145/3580305.3599803), arXiv [2306.06108](https://arxiv.org/pdf/2306.06108.pdf).
- Repo: https://github.com/git-disl/EllipticPlusPlus at commit `08fe6aded83afb97bf5a79a71130f542ca783c2e`. The CSVs there are Git LFS pointers.
- Data: Google Drive folder `1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l`.
- **Licence:** none stated in the repo or README. It is derived from Elliptic, which is CC BY-NC-ND 4.0, so treat it as non-commercial research use only. The README gives a contact address for questions.
- No login is needed.

**2. Fetched here:** yes, five files directly from Drive. Integrity check: the SHA-256 of `AddrTx_edgelist.csv` equals the repo's LFS pointer oid (`f5f903f7…`). Not fetched, because they are not needed for the audit: `wallets_features.csv` (606 MB), `txs_features.csv` (695 MB), `wallets_features_classes_combined.csv` (609 MB) and `txs_edgelist.csv`.

**3. Structure:**
- [computed; matches README] 822,942 addresses: 14,266 illicit, 251,088 licit and 557,588 unknown. That is 1.73% illicit overall and 5.38% among labelled addresses.
- Bipartite memberships: co-input (`AddrTx`) 477,117 and co-output (`TxAddr`) 837,124. Their sum, 1,314,241, equals the README's "addr-tx-addr" count.
- `AddrAddr` has 2,868,964 rows [README], of which 2,775,637 are distinct pairs with no self-pairs [computed].
- [README] 1,268,260 temporal address nodes, 56 features, 49 time steps.
- Labels are at address level. Neither the README nor the actors README states an official split.

**4. Hub audit** [computed with `audit_epp.py`]:

| Relation | Semantics | Group size p50 / p90 / p99 / max (groups ≥2) | >27: groups, memberships share, pairs share | >250: groups, memberships share, pairs share | Illicit rate (labelled): >27 vs others | Illicit rate (labelled): >250 vs others |
|---|---|---|---|---|---|---|
| Co-input (addresses spending in the same transaction) | **genuine shared attribute**: the common-input-ownership heuristic makes a hub by construction | 2 / 10 / 98 / 653 | 1,590; 30.8%; 95.9% | **109; 9.0%; 60.8%** | **0.108 vs 0.042** | **0.169 vs 0.058** |
| Co-output (addresses paid by the same transaction) | shared attribute (the payees of one payer, as in batch payouts) | 2 / 3 / 29 / 13,107 | 2,002; 39.0%; 99.5% | 298; 26.1%; 97.4% | 0.014 vs 0.108 | 0.0003 vs 0.093 |
| Addr-addr | money flow (interaction) | node degree 2 / 11 / 72 / 22,996 | — | — | — | — |

- The hub co-input transactions themselves are labelled 59 licit, 41 unknown and 9 illicit.
- Hubs carry signal in both directions: large co-input groups are enriched for illicit addresses, while large co-output payouts are almost entirely licit. This is the kind of hub an evidence gate should discount or keep.

**5. Fit for each component:**
- **Gate: yes.** Evidence kinds available per pair: co-input, co-output and direct flow (addr-addr). Of the 8.85 M co-input pairs created by transactions with more than 250 inputs, 2.3% co-input again in another transaction, 8.2% are also co-output, and 9.1% have either kind of second evidence [computed]. The gate would therefore drop about 91% of hub-mediated pairs.
- **Incremental inference: yes, at coarse granularity.** All `AddrTx` and `TxAddr` transaction IDs map to an Elliptic time step [computed]. That gives 49 micro-batches. Only 2.7% of input addresses appear in more than one step. The hub transactions fall in 35 of the 49 steps.
- **Labels: yes.** About 32% of addresses are labelled. That is a natural setting for pseudo-labels.

**6. Preprocessing and verdict.**
- Preprocessing: join transaction time steps from the Elliptic features (column 1), or use the "Time step" column in `wallets_features.csv`. Build the bipartite address–transaction incidence. Define a temporal split, for example steps 1–34 and 35–49 following Weber, and state that it is not official for the actors data.
- Memory: the audit peaked at 1.5 GB. Adding the 56 float32 features for 1.27 M rows (about 0.3 GB) gives an estimated total under 3 GB.
- **GO.** Caveats: the licence is unstated, time is coarse, and there are under a million addresses (not millions).

---

### 2.8 AMLworld (IBM; HI and LI, Small, Medium and Large), shortlist #2

**1. Source.**
- Paper: Altman et al., NeurIPS 2023 D&B, arXiv [2306.16424](https://arxiv.org/pdf/2306.16424).
- Data: Kaggle `ealtman2019/ibm-transactions-for-anti-money-laundering-aml`, **version 8, last updated 2025-07-08**. Licence: Community Data License Agreement – Sharing 1.0 [Kaggle API; the paper says CDLA]. Total size 41.6 GB.
- Code: https://github.com/IBM/Multi-GNN at commit `252b0252afca109d1d216c411c59ff70753b25fc`, Apache-2.0.
- `github.com/IBM/AMLworld` does not exist publicly: `git ls-remote` asked for credentials.
- **The data is synthetic.** It comes from a multi-agent generator.

**2. Fetched here:** yes, through the anonymous Kaggle API with per-file URLs. Files: `HI-Small_{Trans.csv, accounts.csv, Patterns.txt}` and `LI-Small_{…}`.

**3. Structure** [computed for Small; compared with paper Table 4]:

| | Transactions | Laundering transactions | Accounts | Days | Entities |
|---|---|---|---|---|---|
| HI-Small (Kaggle v8) | 5,078,345 | 5,177 (0.102%) | 515,088 | 2022-09-01 to 09-18 | 166,207 |
| HI-Small (paper) | 5M | 3.6K | 515K | 10 | — |
| LI-Small (Kaggle v8) | 6,924,049 | 3,565 (0.051%) | 705,907 | 09-01 to 09-17 | 224,931 |
| LI-Small (paper) | 7M | 4.0K | 705K | 10 | — |

- **Discrepancy:** the laundering counts in Kaggle v8 differ from the paper. HI-Small has a 10-day main body plus an 8-day tail of 1,108 transactions, 655 of them laundering, in which laundering patterns complete.
- [paper] Medium HI/LI: 32 M and 31 M transactions, 2.08 M and 2.03 M accounts. Large: 180 M and 176 M transactions over 97 days.
- Labels are at transaction level ("Is Laundering"). For node labels I counted an account as positive if it touches any laundering transaction: 6,357 accounts (1.23%) in HI and 5,304 (0.75%) in LI [computed].
- Ring-level ground truth (synthetic): `Patterns.txt` lists 370 laundering attempts in HI-Small covering 3,209 transaction lines (about 62% of laundering transactions), and 117 attempts in LI-Small. There are eight typologies: fan-in, fan-out, cycle, bipartite, stack, scatter-gather, gather-scatter and random.
- Split: [paper] 60/20/20 temporal. Multi-GNN `data_loading.py` picks day boundaries closest to 60/20/20.
- [paper] "Each entity (person or company) owns one or more bank accounts."

**4. Hub audit** [computed with `audit_aml.py`, HI-Small; LI-Small in brackets]:

| Attribute | Semantics | Size p50 / p90 / p99 / max (groups ≥2) | >27: groups; memberships share; pairs share | >250: groups; memberships share; pairs share | Node-positive rate: >27 vs others | Node-positive rate: >250 vs others |
|---|---|---|---|---|---|---|
| Entity (co-owned accounts) | **genuine shared attribute** (owner) | 4 / 8 / 32 / 7,820 [4 / 9 / 34 / 8,899] | 751; 25.1%; 99.4% | **76; 16.9%; 97.9%** [108; 15.7%; 97.4%] | 0.0087 vs 0.0111 | 0.0079 vs 0.0110 [0.0049 vs 0.0062] |
| Common payee (senders grouped by receiver) | constructible shared attribute | 3 / 5 / 11 / 545 [… / 785] | 596; 3.0%; 43.3% | 2; 0.09%; 8.9% | 0.011 vs 0.016 | 0.000 vs 0.016 |
| Common payer (receivers grouped by sender) | constructible (fan-out hubs) | 2 / 6 / 12 / 14,230 [… / 18,942] | 32; 3.8%; 99.1% | 15; 3.8%; 99.1% | 0.029 vs 0.019 | 0.029 vs 0.019 |
| Bank | coarse shared attribute (institution), not an identifier | 5 / 15 / 424 / 2,639 | 1,577; 73.9%; 99.5% | 556; 50.6%; 89.4% | 0.017 vs 0.0004 | 0.018 vs 0.007 |

**5. Fit for each component:**
- **Gate: yes.** Pairs can have co-ownership, transfers and a shared payee as separate kinds of evidence [computed]:
  - Of the 1.27×10⁸ co-owned pairs, 18,303 also have a direct transfer (1.4×10⁻⁴).
  - 67,989 co-owned sender pairs also share a payee.
  - 2.8% of distinct transacting pairs are intra-entity. Their laundering rate is 0.0007, against 0.0062 for inter-entity pairs.
- **Incremental inference: yes.** Timestamps have minute resolution, with 15,018 distinct timestamps in HI-Small.
- **Labels: yes**, at transaction level, with node labels derived.

**6. Preprocessing and verdict.**
- Preprocessing: account key = `From Bank` + `Account` (as in Multi-GNN). Join `Entity ID` from `accounts.csv`: all 515,088 transaction accounts match. Encode IDs as integers.
- Memory: the audit peaked at 2.1 GB with pandas string IDs. Medium (about 3 GB CSV) needs chunked integer encoding. Large is out of scope.
- **GO** for Small (HI primary, LI as a robustness check). Caveats: it is synthetic, so present it as "realistic synthetic", not real data. Entity hubs are slightly *depleted* in positives, so hub discounting should help here.

---

### 2.9 IEEE-CIS Fraud Detection (Kaggle competition, Vesta), pending local fetch

1. **Source:** https://www.kaggle.com/competitions/ieee-fraud-detection. An IEEE DataPort mirror at https://ieee-dataport.org/documents/ieee-cis-fraud-detection requires a subscription.
   - [DataPort page] Files: `train_{transaction,identity}.csv`, `test_{transaction,identity}.csv` and `sample_submission.csv`, joined by `TransactionID`. The archive is listed at 107.29 MB.
   - [DataPort page] `TransactionDT` is "a timedelta from a reference datetime". The categorical fields are `card1`–`card6`, `addr1`, `addr2`, `P_emaildomain`, `R_emaildomain`, `ProductCD`, `M1`–`M9`, `DeviceType`, `DeviceInfo` and `id_12`–`id_38`. The label is `isFraud`.
   - Licence and competition rules: **not verified.** The Kaggle rules page renders through JavaScript only, so WebFetch got no text.
2. **Fetched here: no.** `https://www.kaggle.com/api/v1/competitions/data/download-all/ieee-fraud-detection` returned **HTTP 401**: it needs a Kaggle login and acceptance of the rules. Local command: Section 4.
3. **Structure:** row counts are not verified (data not obtained). Labels are at transaction level. The test labels are not public, so only the training files carry labels.
4. **Hub audit: not computed (data not obtained).** Constructible shared attributes: `card1` (alone or combined with `card2`–`card6`), `addr1`, `P_emaildomain`, `DeviceInfo` and `id_*` device or browser fields. Whether these values identify individuals or only coarse buckets must be checked on the data. Email domains such as public webmail providers will be giant non-identifying groups.
5. **Fit (expected; verify):**
   - Gate: several attribute kinds per transaction pair.
   - Incremental inference: `TransactionDT` gives an order.
   - Labels: yes.
6. **Verdict: CONDITIONAL.** Run `audit_ieee` (Section 4.4) locally. It would replace YelpChi as #3 if at least one identifier-like attribute (card or device) has groups over 250 that are not pure buckets.

### 2.10 Bank Account Fraud (BAF) suite

- **Source:** Jesus et al., NeurIPS 2022 D&B, arXiv [2211.13358](https://arxiv.org/abs/2211.13358). Kaggle `sgpjesus/bank-account-fraud-dataset-neurips-2022`, version 2.
- **Licence conflict:** Kaggle says **CC BY-NC-SA 4.0**, but the datasheet (A44) says **CC BY-NC-ND 4.0**.
- **Code:** https://github.com/feedzai/bank-account-fraud at commit `3377cfd8…` (Apache-2.0 with a commercial-use notice).
- **Fetched here:** yes, `Base.csv` (delivered as a zip of 86,391,953 B; 213,427,735 B unzipped).
- **Structure** [computed]:
  - 1,000,000 rows and 32 columns; fraud rate 1.10%.
  - `month` runs from 0 to 7. The datasheet (A11) recommends training on months 0–5 and testing on 6–7.
  - Only categorical columns could form groups, and they are not identifiers: for example `device_os` has 5 values, with the largest group at 342,728 rows.
  - [datasheet A10] "There are no relationships between individual instances."
- **Hub audit:** no shared-attribute relation exists. The only fields that could link applications are aggregate velocity counts.
- **Verdict: NO-GO.**

### 2.11 Other datasets in GADBench

- **Source:** Tang et al., NeurIPS 2023 D&B, arXiv [2306.12251](https://arxiv.org/abs/2306.12251). Repo https://github.com/squareRoot3/GADBench at commit `f9aa021ce9b6c6580427fb633b596843be76ddc6` (no licence file).
- **Bundle:** Drive `datasets.zip` (757,193,110 B). It contains amazon, yelp, the hetero amazon and yelp graphs, questions, reddit, tfinance, tolokers, tsocial and weibo. Elliptic and DGraph-Fin must be fetched separately.
- **Splits:** each graph stores 20 masks. Trials 0–9 are fully supervised and trials 10–19 semi-supervised, with 100 training nodes in each case I checked.
- **Hub audit** [computed with `audit_dgl.py`; node-degree proxy]:

| Dataset | Relation [README] | Nodes | Undirected edges | Positive rate | Degree p50 / p90 / p99 / max | Degree >250: nodes (edge share); positive rate >250 vs ≤250 | Sampled clustering | Verdict |
|---|---|---|---|---|---|---|---|---|
| Reddit | under same post | 10,984 | 78,516 | 3.33% | 6 / 24 / 148 / 2,555 | 50 (38.6%); 0.000 vs 0.034 | 0.000 (not a clique projection) | NO-GO: not fraud, no timestamps |
| Weibo | under same hashtag (shared attribute) | 8,405 | 377,271 | 10.33% | 59 / 149 / 632 / 4,359 | 396 (57.5%); 0.028 vs 0.107 | 0.40 | NO-GO: not fraud, groups not recoverable, no timestamps |
| Tolokers | work collaboration | 11,758 | 519,000 | 21.82% | 30 / 235 / 827 / 2,138 | 1,076 (77.1%); 0.362 vs 0.204 | 0.55 | NO-GO |
| Questions | question answering | 48,921 | 153,540 | 2.98% | 1 / 10 / 89 / 1,539 | 116 (31.3%); 0.164 vs 0.030 | 0.07 | NO-GO |

### 2.12 Newer datasets (2024–2026) found

| Dataset | Source | Shared-attribute structure | Size | Labels | Fetched? | Verdict |
|---|---|---|---|---|---|---|
| **TravelFraudBench** (medium preset) | arXiv [2604.21093](https://arxiv.org/html/2604.21093); HF `bsajja7/travel-fraud-graphs` at revision `52451594…`, MIT; code https://github.com/bhavana3/travel-fraud-graphs (HEAD `20106fad…`) | user–device, user–IP, user–card (genuine shared attributes); **synthetic** | 10,000 users, 80 rings | node labels plus `ring_id` | yes (7 files) | **NO-GO.** [computed] Largest group: device 27, IP 23, card 20, so none is over 27. Shared-IP and shared-card members are 100% fraud, which is trivial leakage. [paper] Timestamps are uniform in v1.0. Usable only as a synthetic ring-recovery smoke test |
| **FinFraudBench** (CreditCard-Fraud, BankTrans-Fraud) | arXiv [2608.15177](https://arxiv.org/abs/2608.15177) (Aug 2026); data at https://anonymous.4open.science/r/FinFraudBench-B002 | transaction nodes linked to customer, card, merchant, category and location context nodes (shared attributes by construction) | 1.86 M and 8.99 M nodes [paper] | transaction-level; 0.52% and 0.15% fraud | no (not attempted: anonymous review repo; source tables not named in the HTML I read) | Recheck when the camera-ready release appears. Too large without a subsample |
| **Elliptic2** | arXiv [2404.19109](https://arxiv.org/abs/2404.19109) | Bitcoin cluster graph | 49 M nodes, 196 M edges [paper] | **subgraph-level** (122 K) | no | NO-GO: size; labels are not node-level |
| **FiGraph** (WWW 2025 companion) | https://dl.acm.org/doi/pdf/10.1145/3701716.3715301 | dynamic heterogeneous financial graph (details unverified) | unverified | unverified | no: the ACM fetch failed with a client error | Unverified. Recheck |

---

## 3. Ranked shortlist

| Rank | Dataset | Go / no-go | Why | Main caveats |
|---|---|---|---|---|
| 1 | **Elliptic++ actors** (address level) | **GO** | Real data. Co-input transactions are a genuine shared attribute with 109 groups over 250 members, and those hubs are enriched for illicit addresses (16.9% vs 5.8%). Co-output hubs are almost all licit. Three kinds of evidence (co-input, co-output, flow). 49 time steps order the events. About 32% of addresses are labelled. Peak memory about 1.5 GB | Licence unstated (inherits Elliptic's NC-ND); coarse time (about two weeks per step); no official split for actors |
| 2 | **AMLworld HI-Small** (LI-Small as robustness) | **GO** | Entity co-ownership hubs reach 7,820 accounts (76 groups over 250). Transfers and shared payees give second evidence. Minute timestamps. Temporal 60/20/20 split. `Patterns.txt` adds synthetic ring-level checks. Peak memory about 2.1 GB | **Synthetic.** Labels are transaction-level, with node labels derived. Kaggle v8 counts differ from the paper. Medium needs chunking; Large is out |
| 3 | **YelpChi** | **GO for components 1 and 3; NO-GO for component 2** | Real data, the standard benchmark (CARE-GNN, PC-GNN, GADBench). R-U-R and R-S-R groups are exactly recoverable cliques, with 22 R-S-R groups over 250. Fully labelled | No timestamps. Only 5% of hub pairs have a second relation. Product × star is a weak "attribute". R-T-R does not match its paper definition |
| alt | **IEEE-CIS** | CONDITIONAL | Best semantic match (card, address, email, device) with an event order | Not obtained (login and rules). Hub audit pending |

Excluded: Amazon (groups not recoverable; U-V-U is a similarity), T-Finance (transaction-record edges; no shared attribute; no time), T-Social and DGraph-Fin (millions of nodes, no documented subsample; DGraph also gated), Elliptic (flow only), BAF (no relations), the other GADBench graphs (not fraud; no time), TravelFraudBench (synthetic, no hubs, leakage), and Elliptic2, FinFraudBench and FiGraph (size, label level, or unverified).

---

## 4. Data-fetch script plan (run locally)

Put each dataset in its own empty directory outside the repo, for example `~/data/evidgnn/<name>/`. Kaggle dataset downloads currently work anonymously through the API URL. If they start returning 401, use the `kaggle` CLI with `~/.kaggle/kaggle.json`.

### 4.1 Shortlisted datasets

```bash
set -euo pipefail
B=~/data/evidgnn; mkdir -p $B/{ellipticpp,elliptic,amlworld,yelpchi}

# Elliptic++ (Google Drive file IDs from folder 1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l)
cd $B/ellipticpp
for p in 16eWZTe-dsjEqgsOqFtg78m4fYhcxKlmZ:AddrTx_edgelist.csv 1SYpun0DMDt-h3sbI60G55jNsfwnFTHXg:TxAddr_edgelist.csv \
         1x5JdNWX8fVM3FO8I0wOLDAeh2qaB53uV:AddrAddr_edgelist.csv 1ZaACVE4wSIx7r8Z9ze7ExQnJ0wzGrVkp:wallets_classes.csv \
         1DiBxn8TXdbJqoSw58pYUeaqO3oOKhuQO:txs_classes.csv 1mhrrobYdnaxYBIVK06EpKB2EwV-ERlce:wallets_features.csv \
         19q09IFhfkOOBOXvn_dKhWjILJtjCcsjc:txs_features.csv 1Q2yG_CIDvfdGP-fKVPSw979EYgQukjz5:txs_edgelist.csv; do
  curl -L -o "${p#*:}" "https://drive.usercontent.google.com/download?id=${p%%:*}&export=download&confirm=t"; done

# Elliptic (time steps for Elliptic++ transactions)
cd $B/elliptic && curl -L -o archive.zip https://www.kaggle.com/api/v1/datasets/download/ellipticco/elliptic-data-set && unzip -o archive.zip

# AMLworld Small (HI + LI). Per-file URLs; a file may arrive zipped, so check with `file`
cd $B/amlworld
for f in HI-Small_Trans.csv HI-Small_accounts.csv HI-Small_Patterns.txt LI-Small_Trans.csv LI-Small_accounts.csv LI-Small_Patterns.txt; do
  curl -L -o $f "https://www.kaggle.com/api/v1/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/$f"; done

# YelpChi + Amazon (identical bytes to the CARE-GNN repo copies)
cd $B/yelpchi && curl -LO https://data.dgl.ai/dataset/FraudYelp.zip && curl -LO https://data.dgl.ai/dataset/FraudAmazon.zip && unzip -o FraudYelp.zip && unzip -o FraudAmazon.zip

sha256sum $B/*/* > $B/SHA256SUMS   # compare with Section 6
```

### 4.2 Gated datasets (manual step first)

```bash
# IEEE-CIS: first accept the rules at https://www.kaggle.com/competitions/ieee-fraud-detection/rules while logged in
pip install kaggle && kaggle competitions download -c ieee-fraud-detection -p ~/data/evidgnn/ieee && unzip -o ~/data/evidgnn/ieee/ieee-fraud-detection.zip -d ~/data/evidgnn/ieee
# DGraph-Fin (not recommended): register at https://dgraph.xinye.com, accept https://dgraph.xinye.com/clause, download DGraphFin.zip by hand
```

### 4.3 Optional datasets

```bash
# GADBench bundle (757 MB; includes T-Finance and T-Social, which is 5.6 GB unzipped)
curl -L -o ~/data/evidgnn/gadbench_datasets.zip "https://drive.usercontent.google.com/download?id=1txzXrzwBBAOEATXmfKzMUUKaXh6PJeR1&export=download&confirm=t"
# BAF Base
curl -L -o ~/data/evidgnn/baf_Base.zip "https://www.kaggle.com/api/v1/datasets/download/sgpjesus/bank-account-fraud-dataset-neurips-2022/Base.csv"
```

### 4.4 Audit scripts

I wrote these in the session scratchpad at `/tmp/claude-0/-home-claude/5e05fd61-12b1-5efc-aab4-f0b57c7050a4/scratchpad/scripts/`. They read only. Run each as `nice -n 19 python3 -I <script> …`.

- `audit_mat.py <file.mat> <rel,…>`: YelpChi and Amazon. Clique test, group quantiles, edge shares and label rates.
- `dgl_scan.py` and `audit_dgl.py <dgl file>`: GADBench DGL binaries, read without DGL.
- `audit_aml.py <Trans.csv> <accounts.csv>`: AMLworld entity, payee, payer and bank audit, plus gate evidence.
- `audit_epp.py <ellipticpp dir>`: Elliptic++ co-input and co-output audit.
- `gate_evidence.py <datasets dir>`: second-evidence rates for YelpChi and Elliptic++.
- `audit_ieee` (to write once the data exists): reuse the `report()` function in `audit_aml.py`. Members are `TransactionID`; groups are `card1`, `card1+addr1`, `P_emaildomain` and `DeviceInfo`; label is `isFraud`.

The scratchpad is session-specific. Copy the scripts into the repo (for example `scripts/research/s0b/`) if they need to persist.

---

## 5. What each dataset can and cannot support

| Dataset | Real? | Node labels | Shared-attribute relation with groups >250 | Gate: two or more kinds of evidence per pair | Incremental: timestamps or event order | Label efficiency | Fits 2 cores, 7 GB | Ring-level evaluation |
|---|---|---|---|---|---|---|---|---|
| Elliptic++ actors | real | yes (32% labelled) | **yes** (co-input: 109; co-output: 298) | yes (co-input, co-output, flow) | yes, 49 coarse steps | yes | yes (~1.5–3 GB) | no |
| AMLworld HI/LI-Small | synthetic | derived from transaction labels | **yes** (entity: 76 / 108) | yes (ownership, transfer, payee) | yes, minute timestamps | yes | yes (~2 GB) | synthetic patterns only |
| YelpChi | real | yes (100%) | yes (R-S-R: 22) | weak (5% of hub pairs) | **no** | yes | yes (<1 GB) | no |
| IEEE-CIS | real | transaction-level | unknown (not obtained) | likely | yes (`TransactionDT` order) | yes | likely | no |
| Amazon | real | yes (8,639 usable) | groups not recoverable | partial (one relation is a similarity) | no | yes | yes | no |
| T-Finance | real | yes | no (interaction edges) | no | no | yes | yes (1.8 GB) | no |
| T-Social | real | yes | no | no | no | yes | no (5.8 M nodes) | no |
| DGraph-Fin | real | yes | constructible (shared contact), not audited | partial | partial (time gaps) | yes | no (3.7 M nodes, gated) | no |
| Elliptic | real | yes (23% labelled) | no | no | yes (49 steps) | yes | yes | no |
| BAF | synthetic | yes | no (no relations) | no | months only | yes | yes | no |
| Reddit, Weibo, Tolokers, Questions | real, not fraud | yes | Weibo only (groups not recoverable) | no | no | yes | yes | no |
| TravelFraudBench | synthetic | yes | no (max 27) | yes | no (uniform timestamps in v1.0) | yes | yes | yes, but leaky |

---

## 6. Every URL fetched and every download attempted

Access date for all entries: 2026-10-27.

### 6.1 Code repositories (`git clone --depth 1` or `git ls-remote`)

| Repo | Commit | Licence | Outcome |
|---|---|---|---|
| https://github.com/YingtongDou/CARE-GNN | a64ff7523e187a24251f7ca88435d2c9d8f7dcd9 (2022-10-11) | Apache-2.0 | cloned (83 MB, includes data zips) |
| https://github.com/squareRoot3/GADBench | f9aa021ce9b6c6580427fb633b596843be76ddc6 (2024-06-25) | no licence file | cloned |
| https://github.com/squareRoot3/Rethinking-Anomaly-Detection | de0631f039bbd19c1890b483cc01f1007f596af7 (2024-06-25) | no licence file | cloned |
| https://github.com/PonderLY/PC-GNN | 9d7d7fae491081178b6e12e193fb89cfc330f2be (2021-12-26) | no licence file | cloned |
| https://github.com/git-disl/EllipticPlusPlus | 08fe6aded83afb97bf5a79a71130f542ca783c2e (2023-11-25) | none stated | cloned (CSVs are LFS pointers) |
| https://github.com/feedzai/bank-account-fraud | 3377cfd8fc20edcda3dd9dd14c10ed3dd276c6de (2023-12-21) | Apache-2.0 with a commercial-use notice | cloned |
| https://github.com/IBM/Multi-GNN | 252b0252afca109d1d216c411c59ff70753b25fc (2024-02-13) | Apache-2.0 | cloned |
| https://github.com/DGraphXinye/DGraphFin_baseline | b357023af848b6cd1f976a9ba600ec42a1ec85cf | not checked | ls-remote only |
| https://github.com/IBM/AMLworld | — | — | **failed**: asked for credentials (repo not public) |
| https://github.com/bhavana3/travel-fraud-graphs | 20106fada1c27a5d02ade62a412a5895af51f1dc | MIT (per HF card) | ls-remote only |
| `gh api repos/...` (9 repos) | — | — | **403**: GitHub API not enabled for this session |

### 6.2 Data files downloaded

| File (local name) | URL | Bytes | SHA-256 | Outcome |
|---|---|---|---|---|
| CARE-GNN `data/YelpChi.zip` | repo above | 17,980,652 | 3a31296b951e6c8158dddb783ff2c62709fa987d106bbe21e59f8e119053cec3 | OK |
| CARE-GNN `data/Amazon.zip` | repo above | 26,122,297 | c1b7a1f8cd8621467d5121b690fef61a7d398e4f582232bb3e8a154424f7a5b9 | OK |
| `YelpChi.mat` (unzipped) | — | 207,676,376 | fedb35a8fa539b27866244d3515a47a76b20080cdacb33112da3458fd2487b42 | — |
| `Amazon.mat` (unzipped) | — | 222,634,416 | 4b7e3f9cccc62b736792707393ccd74332a1a0592dba128ac6b2989bf1ee9d63 | — |
| FraudYelp.zip | https://data.dgl.ai/dataset/FraudYelp.zip | 17,980,652 | 3a31296b…53cec3 (identical) | 200 |
| FraudAmazon.zip | https://data.dgl.ai/dataset/FraudAmazon.zip | 26,122,297 | c1b7a1f8…f7a5b9 (identical) | 200 |
| GADBench `datasets.zip` | https://drive.usercontent.google.com/download?id=1txzXrzwBBAOEATXmfKzMUUKaXh6PJeR1&export=download&confirm=t | 757,193,110 | da8b8ec2386d5042d9bbc3dc7f1873e4267b986bf0272b8760cf9b5628df7304 | 200 |
| ↳ `tfinance` | (inside zip) | 1,023,882,459 | 8f3b05272703220bb3248b0caac92e917c7524704094c02f802b400026ed1d38 | extracted |
| ↳ `weibo` | (inside zip) | 24,017,643 | 111402a2cb3b6a10ec586e96122da809d62bfe3617add07cb006de53fc109f05 | extracted |
| ↳ `reddit` | (inside zip) | 7,596,471 | 575caca42abdb659cda700174854f7c1542d0cb7f79f676612d4a8385142a0fa | extracted |
| ↳ `tolokers` | (inside zip) | 7,644,231 | 4943a2a16b2501a13ec26d05b0318596b75b897c8c92f55730f4e7c466d4c1ef | extracted |
| ↳ `questions` | (inside zip) | 64,662,315 | d19445f0e396bd163a048a436de94f50efa2048b0a59da184e5c0cf6b5641d79 | extracted |
| BAF `Base.csv` (arrived as zip) | https://www.kaggle.com/api/v1/datasets/download/sgpjesus/bank-account-fraud-dataset-neurips-2022/Base.csv | 86,391,953 | 3fec019ec7050060c5b8288562ebaaa4a0b76ed18741c4e4ccd2d13ccd12c02c | 200 |
| ↳ `Base.csv` (unzipped) | — | 213,427,735 | 7bf10a37ce07e72e14c1b09e5efee3d27261baff4facc7da767b0474dcf9b809 | — |
| Elliptic per-file (3 files) | …/datasets/download/ellipticco/elliptic-data-set/elliptic_bitcoin_dataset/<file> | ~5.5 KB each | (HTML pages) | **404** |
| Elliptic bundle `archive.zip` | https://www.kaggle.com/api/v1/datasets/download/ellipticco/elliptic-data-set | 153,218,318 | 70ed052c52002392720615a03261039b62d1ad594f6081ad021cb174a8ad5717 | 200 |
| ↳ `elliptic_txs_classes.csv` | — | 3,305,144 | 93e2e7b2405c735ba752bf6ba06b947561deddd1f5a8fc91e46f6a4c0e439493 | — |
| ↳ `elliptic_txs_edgelist.csv` | — | 4,470,584 | a35053ba68a98e4382cae2ba65b9d9e36b23b6439e02dff084971b1b72a5156e | — |
| ↳ `elliptic_txs_features.csv` | — | 689,683,771 | fd7f83573443c9e302e371d3f110e3b6224160f5d1ed8a287757936127800ff0 | — |
| AMLworld `HI-Small_Trans.csv` | …/datasets/download/ealtman2019/ibm-transactions-for-anti-money-laundering-aml/HI-Small_Trans.csv | 475,664,283 | b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040 | 200 |
| AMLworld `HI-Small_accounts.csv` | (same pattern) | 34,053,187 | 786808526e33cfc441212dd6fccda7edfc24172149bed59c6ef59b186836b014 | 200 |
| AMLworld `HI-Small_Patterns.txt` | (same pattern) | 323,844 | 2c546b5ce6009e73851f0139af053cf845f08bf92f3bc82fe1eb937dec2ef39b | 200 |
| AMLworld `LI-Small_Trans.csv` | (same pattern) | 650,422,357 | f7a9940339c78b5d1476071505b5867c0f5319640b9c4279d13f531bf965319d | 200 |
| AMLworld `LI-Small_accounts.csv` | (same pattern) | 47,248,016 | f51322afe81859fefc58b09cae6068dbdacce78cd9dfb9ef2b693e5190ec4718 | 200 |
| AMLworld `LI-Small_Patterns.txt` | (same pattern) | 99,156 | 734c15b7ff4be1a04a3529bd1524b92c1e8b62289d3ce4881423596ee47a208f | 200 |
| Elliptic++ `AddrTx_edgelist.csv` | https://drive.usercontent.google.com/download?id=16eWZTe-dsjEqgsOqFtg78m4fYhcxKlmZ&export=download&confirm=t | 21,248,388 | f5f903f752387f66a1bccaeff54e293b2e8470fcddf5eb56b88aa06fd23a8f3b (= LFS oid) | 200 |
| Elliptic++ `TxAddr_edgelist.csv` | …id=1SYpun0DMDt-h3sbI60G55jNsfwnFTHXg… | 36,702,878 | 9f5afbdde7bc3d91fb7a4655be55799d6504cd0063ae55a0753a5a41189932b8 | 200 |
| Elliptic++ `txs_classes.csv` | …id=1DiBxn8TXdbJqoSw58pYUeaqO3oOKhuQO… | 2,361,914 | 013a11742969071a906878ded0319571df0657f9b7133e5c6cdb36217bf0d240 | 200 |
| Elliptic++ `wallets_classes.csv` | …id=1ZaACVE4wSIx7r8Z9ze7ExQnJ0wzGrVkp… | 30,421,134 | 4e5132c99f941666bf1fefd4100a1428d339c9252ec6987909e1adf8eac902f9 | 200 |
| Elliptic++ `AddrAddr_edgelist.csv` | …id=1x5JdNWX8fVM3FO8I0wOLDAeh2qaB53uV… | 200,631,481 | ffba894458e262a691e5e4d006f5dc1d0e069fabfe828f443fd157bf7f8393f2 | 200 |
| Elliptic++ 4 other files | HEAD requests only (IDs in Section 4.1) | 606–695 MB each; txs_edgelist 4.47 MB | — | not downloaded |
| TravelFraudBench `medium/metadata.json` | https://huggingface.co/datasets/bsajja7/travel-fraud-graphs/resolve/5245159442d912f4e1f221618d867908f027480d/medium/metadata.json | 388 | a13a33957275c416f0cbfc2050f5d0b0d938c2e8f8a64e8c3bfa655018ab2e10 | 200 |
| TravelFraudBench `medium/nodes/user.csv` | (same base)/medium/nodes/user.csv | 474,093 | 3b4aed2a6f6aa436f31453fa3e81b8f99d06f548f57dd9ab2c754dec1c4f9a1f | 200 |
| TravelFraudBench `…user__uses_device__device.csv` | (same base)/medium/edges/… | 202,608 | 244baad0a0e04bb13732c805270c38d49a8e5a7a36d28997c0d08800c34a6ffd | 200 |
| TravelFraudBench `…user__uses_ip__ip_address.csv` | (same base) | 289,145 | ae4bec9c3d9bec407d108bf5ad9019270dbc84d655a52ae3b34dc475ba3d1ed2 | 200 |
| TravelFraudBench `…user__owns_card__payment_card.csv` | (same base) | 143,245 | 37395e2e0e175abca0f06040bdf6ac035f55e7fb4c8b87d8851ccfa1dfb765a8 | 200 |
| TravelFraudBench `…user__made__booking.csv` | (same base) | 313,442 | 8db988631a3234deefc76675dc19676af9a944d3efc5f3f59c8fea04bcf8e8c2 | 200 |
| TravelFraudBench `…booking__paid_with__payment_card.csv` | (same base) | 315,524 | ea1091972591e2f50a28a3333dc550713170718c0bb66030a83f9e5308009132 | 200 |

### 6.3 Probes, metadata calls and failed attempts

| URL | Outcome |
|---|---|
| https://raw.githubusercontent.com/YingtongDou/CARE-GNN/master/README.md | 200 (reachability probe) |
| https://www.kaggle.com, https://huggingface.co, https://zenodo.org | 200 (probe) |
| https://drive.google.com | 302 (probe) |
| https://drive.google.com/drive/folders/1PpNwvZx_YRSCDiHaBUmRIS3x1rZR7fMr (T-Finance folder page) | 200 HTML. **By mistake this was saved to `/tf_folder.html` at the filesystem root** (an unset shell variable). A safety check blocked the cleanup, so the user should delete it |
| https://drive.google.com/drive/folders/1MRPXz79Lu_JGLlJ21MDfML44dKN9R08l (Elliptic++ folder page) | 200 HTML, parsed for file IDs |
| https://www.kaggle.com/api/v1/datasets/download/{AMLworld, BAF, Elliptic} (whole bundle; probe only) | 302 to signed GCS URL (anonymous access works) |
| https://www.kaggle.com/api/v1/datasets/list/… and …/datasets/view/… (3 datasets) | 200 JSON (file lists, versions, licences) |
| https://www.kaggle.com/api/v1/competitions/data/download-all/ieee-fraud-detection | **401** (login and rules required) |
| https://www.kaggle.com/api/v1/competitions/data/list/ieee-fraud-detection | **401** |
| https://www.kaggle.com/api/v1/competitions/list?search=ieee-fraud-detection | 200, but the response was not a list (no usable metadata) |
| https://dgraph.xinye.com/dataset | **CONNECT tunnel failed, 502** (blocked or unreachable from this sandbox) |
| https://huggingface.co/api/datasets/bsajja7/travel-fraud-graphs | 200 JSON (revision, licence, file list) |

### 6.4 Web pages read (WebFetch)

| URL | Outcome |
|---|---|
| https://arxiv.org/abs/2008.08692 | OK: relation definitions and Table 2 |
| https://arxiv.org/abs/2207.03579 | abstract only |
| https://arxiv.org/pdf/2207.03579 | OK: DGraph-Fin statistics, access terms, split |
| https://proceedings.mlr.press/v162/tang22b.html | abstract only |
| https://proceedings.mlr.press/v162/tang22b/tang22b.pdf | OK: T-Finance and T-Social descriptions |
| https://arxiv.org/abs/2306.16424 | abstract only |
| https://arxiv.org/pdf/2306.16424 | OK: AMLworld Table 4, entities, split, CDLA |
| https://arxiv.org/abs/2211.13358 | abstract only; BAF details taken from the datasheet PDF in the cloned repo |
| https://www.kaggle.com/competitions/ieee-fraud-detection/data | JavaScript shell, no content |
| https://www.kaggle.com/competitions/ieee-fraud-detection/rules | JavaScript shell, no content |
| https://www.kaggle.com/c/ieee-fraud-detection/discussion/101203 | JavaScript shell, no content |
| https://ieee-dataport.org/documents/ieee-cis-fraud-detection | OK: file list, column groups, subscription required |
| https://arxiv.org/abs/1908.02591 | abstract only |
| https://arxiv.org/pdf/1908.02591 | OK: time steps, label counts, split |
| https://arxiv.org/abs/2608.15177 and https://arxiv.org/html/2608.15177 | OK: FinFraudBench statistics |
| https://arxiv.org/html/2604.21093 | OK: TravelFraudBench |
| https://dl.acm.org/doi/pdf/10.1145/3701716.3715301 | **failed** (client error) |
| https://arxiv.org/abs/2404.19109 | OK: Elliptic2 |
| https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.datasets.DGraphFin.html | OK: statistics only, no download URL |
| https://www.dgl.ai/dgl_docs/generated/dgl.data.FraudDataset.html | OK: default split 0.7/0.1, seed 717 |

Web searches (4): IEEE-CIS data description; 2025 graph fraud datasets with shared device or IP (extended); FiGraph GitHub; IEEE-CIS competition rules. Result pages used are listed above.
