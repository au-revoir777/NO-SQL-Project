# Prompt 2: INPUT CHECK and N1 (novelty audit)

Source: `paper_refinement_prompt2.txt`. Branch `feat/paper-refine` at `45c27c0`.
`paper.pdf` and the LaTeX sources were built from the same commit, so the
`.tex` text is treated as the PDF text.

## 1. Input check

| Input | Received | Notes |
|---|---|---|
| paper.pdf | yes | `docs/paper/paper.pdf` (45c27c0) |
| LaTeX | yes | `paper.tex`, `sections/*.tex`, `tables/*.tex`, `numbers.tex` |
| Code | yes | `src/fraudsim/` (read: `graph/store.py`, `detectors/engine.py`, `detectors/hubaware.py`, `detectors/static_cypher.py`, `experiments/suite.py`, `experiments/weight_functions.py`) |
| Result CSVs | yes | `results/*/results.csv` (recomputed from `e3_frontier`, `e5_hub_size`) |
| Scenario YAMLs | yes | `configs/scenarios/*.yaml` |
| Protocols | yes | `docs/research/e*_protocol.md`, `e*_results.md` |
| REPRODUCE.md | yes | not executed |
| Web search | yes | prior-art statements below come from searches I ran; every one is VERIFY |

Cannot verify without more work:
- Any number that needs a rerun. I re-ran no experiments.
- The cause of two observed effects, which needs per-ring traces: the constant weight losing rings under the 250 limit, and full recomputation differing from incremental at 500 and 2,000-user hubs.
- Full texts behind paywalls. For FRAUDAR, Spade and Spade+ I read the text; for meta-blocking I read a survey; other prior art is from search hits only.
- Whether the cited references say what the paper says (R8), and REPRODUCE.md from a clean checkout (P1).

## 2. N1 audit: C1 to C4

| | Claim sentence (strongest honest form) | Closest prior work (VERIFY) | New vs applied | Reviewer dismissal | Verdict |
|---|---|---|---|---|---|
| **C1** | "For shared-attribute ring detection on a stream, accumulating decayed attribute and transfer evidence per pair separates rings from the busy attributes they share, which per-attribute grouping rules cannot, because a rule emits the whole attribute group." (The paper's own sentence, "keeping hub links is what matters", is not supported; see section 5.) | FRAUDAR column weight 1/log(x+c), c=5, argued against 1/x (Hooi et al., KDD 2016; TKDD 2017 text read). Spade (Jiang et al., PVLDB 16, 2022): incremental peeling with 1/log(deg+5) on Grab transaction graphs. Spade+ (2022 tech report): adds deletions. Adamic–Adar. Entity-resolution meta-blocking: ARCS weight "sums the inverse cardinalities of the common blocks"; Block Purging "discards blocks that exceed an upper limit", the same cap-versus-discount choice. Liu (arXiv 2512.19061, 2025): summed soft links via shared device/IP on real payment data. | Applied. The discount and the pairwise sum over shared groups both exist. | "This is FRAUDAR's weighting, or ARCS meta-blocking, on a user–attribute graph, and your own results say the weight doesn't matter." | **Not novel** as a weighting. The keep-links vs cap comparison is an empirical finding whose current attribution is wrong. |
| **C2** | "Re-evaluating only the k-hop region a micro-batch touches, with fan-out limits, gives the same rings as a full pass when no pair can reach θ_e through over-limit attributes alone, at a cost that does not grow with the graph." | Spade and Spade+: exact incremental peeling ("peeling sequence is identical" to recomputation), same weighting, real transaction graphs; code at github.com/samjjx/Spade. DenseAlert (Shin et al., KDD 2017): incremental dense subtensors. MIDAS (Bhatia et al., AAAI 2020 / TKDD 2022): per-edge scores, constant memory. Incremental community detection: delta-screening (Zarayeneh et al., TNSE 2021), dynamic Leiden (Sahu, arXiv 2024). Fan et al., "Incremental graph computations: doable and undoable" (SIGMOD 2017): relative boundedness. | Applied. Dirty-region recomputation is standard. The one specific element is the first-hop safety inequality h(L+1) < θ_e: an inequality, not a result, and it holds only for k = 1 over-limit attribute. | "Recomputing the neighbourhood of changed nodes is textbook incremental processing, and Spade already maintains exact weighted peeling incrementally." | **Incremental** (engineering). Novel only if N-A holds as a stated, tested condition. |
| **C3** | "Logistic regression with isotonic calibration over 19 ring features supplies most of the precision for every candidate generator, and every alert carries contributions, evidence and counterfactuals." | Zadrozny & Elkan 2002; Niculescu-Mizil & Caruana 2005; Azbergen et al. 2026 (AML calibrators); counterfactual robustness and consistency literature already cited. | Applied. The two transferable findings are measurements: the isotonic-interpolation defect (0/103 → 103/103 valid) and ring-level miscalibration from scoring the max over snapshots. | "Logistic regression plus isotonic calibration with linear contributions is standard." | **Not novel**. The defect is a useful small finding. |
| **C4** | "A seeded simulator with ring-level ground truth, shared-attribute hubs and five evasion strategies makes every component testable on identical streams." | AMLSim (IBM); AMLworld (Altman et al., NeurIPS 2023); PaySim (Lopez-Rojas); TravelFraudBench (Sajja, arXiv 2604.21093, 2026: ring-level ground truth with shared device/IP clusters, but static, with no camouflage or adversary). | Applied (artifact). It differs from the above by combining hubs, evasion, streaming and a hidden ledger. Realism is not validated. | "A simulator built by the same authors who designed the detector; hub hiding is defined the way your detector catches it." | **Incremental** (artifact). It counts only if released with documentation, and the circularity must go into Threats. |

Searches run: FRAUDAR weighting; Spade / Spade+; DenseStream / DenseAlert; MIDAS; incremental Leiden / delta-screening; incremental graph computation boundedness; meta-blocking weighting and purging; fraud-ring simulators; group fraud with calibration and explanations; shared-attribute fraud rings with hub or degree-cap handling (two queries); bounded-neighbourhood exactness for incremental dense subgraphs.
- I found no paper that states a sufficient condition under which a fan-out-limited dirty region misses no pair a full pass would link, for a degree-discounted pair weight. The search was not exhaustive.
- I found no paper comparing a degree cap with a degree discount for shared-attribute fraud rings under hub-hiding evasion. The ER meta-blocking literature compares purging with weighting for entity matching, not fraud.

## 3. Where the defensible novelty sits now

Defensible today, all as measured findings rather than methods:

1. **Gain attribution.** The scorer accounts for 0.35 of the 0.52 F1 gap over the rules (0.21 → 0.56). The remaining 0.17 (0.56 → 0.73) is unattributed until R1 runs.
2. **The cap is not the mechanism.** This is new from the CSVs. Without the scorer, the rule baseline's recall on shared-attribute rings is 0.55 at every cap from 5 to 200 (`results/e3_frontier`). Caps of 50, 100 and 200 are at or above every benign hub in those four scenarios (largest 50). With the cycle rule off, cap 10 finds 5 of 15 hub-hiding rings at every hub size from 5 to 200 (`results/e5_hub_size`). So the rules miss these rings for a reason other than the cap. The code points to the cause: Q1, Q2 and Q4 each emit one group per attribute (`static_cypher.py`), and a 4-member ring inside a group of 9 or more fails the Jaccard 0.5 match whatever the cap. The degree cap also applies only to the IP rule; devices and cards are uncapped. The defensible C1 is therefore pairwise evidence accumulation vs per-attribute grouping. Whether a cap hurts within a pairwise detector is exactly the untested R1 control.
3. **Bounded-region safety depends on the weight.** This is the only result tying the weight's shape to anything. Today it is an inequality plus 9/15 vs 12/15 (n = 5, p = 0.25), and the stated mechanism does not match the code (section 5, item 3).
4. **The isotonic counterfactual defect.** Small, but it transfers to any system that aims counterfactuals at calibrator breakpoints.

Where the paper claims beyond this:
- The title's "Hub-Aware". A constant does as well, and the weight's shape is not what separates the methods.
- Abstract: "hides any ring behind such a hub", and "a 5 s timer cannot keep up" (one size).
- C1: "keeping hub links is what matters" and "caps lose rings hidden behind hubs".
- C1 and Related Work: novelty of applying the discount "on a stream" (Spade already does, on a different graph).
- C2: "pays off as the graph grows" (one point).
- C3: "calibrated" (ECE 0.10 at ring level) and "each alert carries … counterfactuals" (81 of 262).
- Conclusion: "a recall … that no cap reaches", "strong discounts and soft caps lost the rings" (thresholds at the grid edge), "evade all methods".

## 4. Claims ledger, version 1

Evidence seeds: test seeds 1001+ unless noted; validation seeds 301–303. "Own scorer" means a scorer trained on that method's own candidates; none exists yet.

| ID | Claim (short) | Type | Evidence | Strongest comparator | Attributable to | Status | Allowed wording |
|---|---|---|---|---|---|---|---|
| A1 | Caps hide any ring behind a hub | mechanism (of baseline) | Fig. 6 (65/90); Fig. 7 (33/52); e3 caps 5–200 flat at 0.55 | rules with cycle rule | n/a | **unsupported** | "Per-attribute grouping rules do not separate a ring from a busy attribute it shares; in our runs their recall on such rings did not depend on the cap." |
| A2 | 0.73 vs 0.21; same scorer 0.56; scorer is most of the gap | superiority | Table II, 5×10 seeds, Holm p<0.001 | cap 10 + shipped scorer (not own scorer); GB over Louvain 0.555 | scorer 0.35; remainder unattributed | **partly** | As is, plus "the remaining 0.17 is not yet attributed" until R1 |
| A3 | Keeping hub links raises reachable recall 0.53 → 0.81 | mechanism | Fig. 4 (4×5 seeds, cycle rule off, max over θ_a; no CI on recall) | cap 10 + scorer | pairwise detector vs grouping rule, not the cap | **partly** | "On shared-attribute rings, the pairwise detector with the scorer reaches recall 0.81 against 0.53 for the cap-10 rules with it; without the scorer no cap from 5 to 200 exceeds 0.55." |
| A4 | Exact discount matters little | non-inferiority | E2c (5×10 seeds): const 0.76 p=0.187, √ 0.74 p=0.504; 1/d 0.62, soft 0.68 | shipped weight | n/a | **partly** (no TOST, thresholds at the grid edge) | "No significant F1 difference among 1/ln(1+d), 1/√d and a constant (not an equivalence test)." |
| A5 | Incremental buys nothing over a 1 s timer on small graphs | limitation | E4b, 25 runs, p=0.624 | 1 s timer | n/a | **supported** | As is |
| A6 | Affordable as graph grows; 5 s timer cannot keep up | efficiency | E4b growing hubs, 3 seeds; one point (20,000) | 5 s timer | engine | **partly** | "At 20,000 users with growing hubs (3 seeds)…" |
| A7 | Slow and rotating rings evade every method | limitation | Fig. 7 4/14, 3/13; RQ9 cap 10 recovers 0.42–0.75 of slow rings at precision ~0.04 | cap 10 | n/a | **partly** | "…are rarely found by any method; rules recover more slow rings only at precision near 0.04." |
| A8 | All positive results synthetic | limitation | §VI, public data | n/a | n/a | **supported** | As is |
| C1a | Discount is FRAUDAR's; contribution is its use for shared-attribute rings on a stream | novelty | Related Work | Spade/Spade+ (VERIFY) | n/a | **partly** | "…on shared-attribute pairs, where Spade applies it to transaction peeling" |
| C1b | Keeping hub links is what matters | mechanism | A3 evidence; no capped pairwise control | n/a | not isolated | **unsupported** | Pending R1 |
| C1c | Constant weight with own threshold performs as well | non-inferiority | E2c | shipped | n/a | **partly** | As A4 |
| C1d | Caps lose rings hidden behind hubs | mechanism | as A1 | rules | n/a | **unsupported** | As A1 |
| C2a | Bounded region; pays off only as graph grows | efficiency | E4, E4b | 5 s timer | engine | **partly** | As A6 |
| C2b | Incremental gives the same rings as full | exactness | Table V (20 runs identical); E8 52/52; E5b not identical (3/5 at 500, 2/5 at 2,000) | full pass | region rule | **partly** | "…in every accuracy run (hubs ≤ 50); at 500 and 2,000-user hubs runs differed but found no fewer hub-hiding rings" |
| C3a | Calibrated classifier | mechanism | snapshot isotonic; ring ECE 0.10 | ring refit (Brier 0.044) | n/a | **partly** | "calibrated on snapshots; miscalibrated at ring level" |
| C3b | Scorer supplies most precision, ours and baselines' | mechanism | Table V 0.28→0.75; Table II 0.14→0.64 | n/a | scorer | **supported** | As is |
| C3c | Each alert carries contributions, evidence, counterfactuals | artifact | RQ8: 81/262 have a counterfactual | n/a | n/a | **unsupported** as worded | "…and, where one exists (81 of 262 alerts), a single-feature counterfactual" |
| C4 | Simulator with ground truth, five evasion strategies, paired design with CIs | artifact | code, Table I | AMLworld, TravelFraudBench (VERIFY) | n/a | **supported** (realism unvalidated) | Add circularity to Threats |
| K1 | Keeping links reaches a recall no cap reaches | mechanism | as A3 | rules | not the cap | **partly** | As A3 |
| K2 | Constant as good; strong discounts and soft caps lost hub rings | non-inferiority + mechanism | E2b/E2c; 3 of 5 thresholds at the grid edge | shipped | n/a | **partly** | Qualify with grid edge (R6) |
| K3 | Scored cap 0.56 vs 0.73; scorer most of the gain | superiority | Table II | cap 10 + scorer | scorer | **supported** | As is, plus the remainder caveat |
| K4 | At best operating point, weight and cap indistinguishable | null | Fig. 4, CI −0.03 to 0.10 | cap 10 + scorer | n/a | **supported** | As is |
| K5 | Region gave same rings as full in every accuracy run | exactness | Table V | full pass | region | **supported** (scoped) | As is |
| K6 | Small graphs: no cheaper, no faster than 1 s timer | limitation | E4b | 1 s timer | n/a | **supported** | As is |
| K7 | 20,000 users: 173 vs 4,170 ms; timer can't keep up | efficiency | E4b, 3 seeds | 5 s timer | engine | **supported** (single point) | Keep "at 20,000 users" |
| K8 | Slow and rotating rings evade all methods | limitation | as A7 | | | **partly** | As A7 |
| K9 | Neo4j/Redis: same rings, slower, store-bounded | equivalence + efficiency | E8 52/52 | in-memory | n/a | **supported** | As is |
| K10 | GB over rule-free groups: more precise, half the recall, collapses under decoys | superiority (robustness) | RQ9: P 0.94 vs 0.76, R 0.38 vs 0.74; decoy 0.05 vs 0.74–0.82 | GB + Louvain | candidate generator (vs Louvain grouping) | **supported** | As is |
| K11 | Counterfactual defect fixed; 81/262 have one; retrain changes it | measurement | RQ8 | n/a | n/a | **supported** | As is |
| K12 | Evidence shows the right accounts; explanation untested | limitation | RQ8 | n/a | n/a | **supported** | As is |

### W1 preview: every "better than" or "as good as" claim

| Claim | Type | Status |
|---|---|---|
| Pipeline beats unscored rules (0.73 vs 0.21) | superiority | supported, but not attributable to C1 |
| Pipeline beats scored rules (0.73 vs 0.56 / 0.52) and scored Louvain (0.41) | superiority | supported (shared scorer, not own scorer; distribution shift) |
| Pipeline beats GB over Louvain groups (0.73 vs 0.555) | superiority | supported (p<0.001) |
| Hub weighting beats the cap (best F1) | superiority | **unsupported** (CI −0.03 to 0.10); the paper already says so |
| Hub weighting reaches higher recall than the cap | superiority (recall only) | supported as a number; attribution to the cap unsupported |
| Constant / 1/√d as good as 1/ln | non-inferiority | **partly** (no TOST) |
| 1/ln better than 1/d and soft cap | superiority | **partly** (p<0.001 for 1/d over 5 scenarios, soft p=0.159; thresholds at the grid edge) |
| Incremental as good as full (same rings) | equivalence | supported for hubs ≤ 50; not identical at 500/2,000 |
| Incremental beats 1 s timer on small graphs | efficiency | **unsupported** (the paper says it does not) |
| Incremental beats 5 s timer at scale | efficiency | supported at 20,000 only (3 seeds); loses at 1,000 and 5,000 |
| 250 limit as good as no limit for 1/ln (hubs to 10,000) | non-inferiority | partly (5 seeds per size, one scenario; no full reference at 10,000) |
| Constant worse under the limit than without | superiority (of full) | **unsupported** statistically (9/15 vs 12/15, p=0.25) |
| Tuned thresholds beat a-priori (0.73 vs 0.68) | superiority | supported (p=0.034, Holm family unclear: R7) |
| Pipeline withstands decoys better than Louvain / GB | robustness | supported |
| Adaptation does not lower detection (18/22 vs 9/11) | non-inferiority | **partly** (small n, no interval) |

## 5. Inconsistencies the audit exposes

1. **Cap value does not change rule recall** (CSVs, above). This contradicts the abstract ("hides any ring"), C1 ("caps lose rings hidden behind hubs"), the Fig. 4 text ("invisible to every cap") and the conclusion ("no cap reaches").
2. **The "degree cap" applies only to the IP rule.** Devices and cards are uncapped (`static_cypher.py`; §IV-D says this correctly). The abstract and introduction speak of capping shared attributes in general, and `hub_heavy` has a kiosk device hub that no cap touches.
3. **The constant weight's loss under the 250 limit is unexplained.** §III-C says a constant "lets one busy attribute reach the threshold". But at θ_e = 1.0, one constant attribute gives 1.0 × decay < 1.0 for any link older than the batch time (`hubaware.py`: `decay`, `>=`). So a single attribute does not reach the threshold. The 9/15 vs 12/15 needs a per-ring trace before any mechanism is stated.
4. **"Costs nothing" holds only for one over-limit attribute.** In fan-out mode the first hop skips every over-limit attribute (`store.py`, `continue`), so a pair sharing two of them (≈ 0.36 ≥ 0.3) never enters the region. The "bound" rule covers this case, and in E5b it never added a user. This resolves N-A's "check first": the transfer term is not a hole, because transfers are expanded with no fan-out limit at every hop. The gaps are k ≥ 2 over-limit attributes, and weight decreases (decay, hub growth) on pairs that no event touches.
5. **Full recomputation is not identical at large hubs** (E5b: 3/5 runs at 500, 2/5 at 2,000). §III-C's argument covers only pairs linked through the first hop. The other differences come from elsewhere. My hypotheses, unverified: the later-hop limit of 20, or untouched pairs whose weight fell. C2's exactness is scoped to the accuracy scenarios, and N-A must cover this.
6. **"Above a few thousand users the timer cannot keep up"** (RQ2) contradicts the 5,000-user point. There the 5 s timer costs 371 ms per simulated second, so it keeps up; only 20,000 exceeds 1 s.
7. **"Slow rings evade every method"** (abstract, RQ3, conclusion) contradicts RQ9, where cap 10 recovers 0.42–0.75 of slow rings at precision near 0.04.
8. **C3 says every alert carries counterfactuals.** RQ8 says 81 of 262 do.
9. **C3 says "calibrated".** RQ7 reports ring-level ECE 0.10.
10. **The constant's θ_e = 1.0 is not a natural bound.** Above 1.0 the rule still means "a second attribute or transfers", so the edge selection is a real grid edge (R6).
11. **Novelty of "on a stream".** The intro credits the discount's use on a stream as the contribution, while Related Work describes Spade applying the same discount incrementally to transaction graphs. The difference (shared-attribute pairs, not transaction peeling) is not stated in C1.
12. **Mechanical.** Fig. 7 caption: `Table~` followed by a stray carriage return before `ef{tab:baselines}` (R7).

## Open questions

1. Finding 2 shifts C1 from "discount instead of cap" to "pairwise evidence instead of per-attribute grouping". R1's control (the pairwise detector with a cap) is what decides whether the cap matters at all. I would move R1 ahead of W2. Agree?
2. May I run diagnostic traces (no new claims, no new seeds) on the existing E5b streams? Seeds 1001–1005 at the 500-user hub, to explain the constant's 9/15 vs 12/15 and the non-identical full runs. The results would inform N-A's wording only, not any table.

## Sources

- Hooi et al., Graph-Based Fraud Detection in the Face of Camouflage (TKDD 2017): https://alexbeutel.com/papers/tkdd_fraud_detection_with_camo.pdf
- Jiang et al., Spade (PVLDB 16): https://arxiv.org/pdf/2211.06977 ; https://www.vldb.org/pvldb/vol16/p461-jiang.pdf
- Jiang et al., Spade demo (PVLDB 17): https://vldb.org/pvldb/vol17/p4253-jiang.pdf
- Jiang et al., Spade+: https://csjxjiang.github.io/SpadePlus.pdf
- Shin et al., DenseAlert: https://arxiv.org/pdf/1706.03374
- Bhatia et al., MIDAS: https://arxiv.org/pdf/2009.08452
- Zarayeneh & Kalyanaraman, delta-screening: https://eecs.wsu.edu/~ananth/papers/Zarayeneh_TNSE21-earlyaccess.pdf
- Sahu, dynamic Leiden: https://arxiv.org/html/2410.15451v1
- Fan et al., Incremental graph computations: https://homepages.inf.ed.ac.uk/wenfei/papers/sigmod17-Inc.pdf
- Papadakis et al., blocking and filtering survey: https://arxiv.org/pdf/1905.06167
- Liu, large-scale graph clustering with heterogeneous link transformation: https://arxiv.org/html/2512.19061
- Sajja, TravelFraudBench: https://arxiv.org/pdf/2604.21093
