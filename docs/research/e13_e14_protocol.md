# E13 learned baseline and E14 evasion strength (protocol)

Workstreams A4 and A5 of the Phase 2 plan (`docs/phase2/phase2_prompt.md`,
P12, where the sweep is called "E11 evasion_strength"; E11 was taken, so the
numbering here is E13 and E14). This protocol is committed **before** any E13
or E14 result is computed. Later changes go under "Amendments" with their
reason.

## E13: a learned tabular baseline under the E1 protocol

**Question.** Does the hand-designed rule stage (hub-aware weighting, cycle and
smurfing rules) earn its place? Or does a learned classifier on the same ring
features, over rule-free candidate groups, do as well?

**Method `tabular_gb`, fixed before results:**
- **Candidates without a rule stage:** connected components of the
  shared-attribute and transfer graph, recomputed every 5 simulated seconds.
  This is E1's `plain_cc` grouping (weakly connected components, no density
  filter, no degree cap) and the only candidate generator. Tracking and
  hysteresis are the same as for every E1 method.
- **Scorer:** gradient boosting (scikit-learn `HistGradientBoostingClassifier`
  through `RingScorer("gradient_boosting")`) on the **same 19 ring features**,
  with isotonic calibration. It is trained exactly as the shipped scorer: same
  six scenarios, **training seeds 101–110**, the same fit/calibration split by
  time (0.7), and the same label (Jaccard ≥ 0.5 with a true ring's all-time
  members). The training rows are its own candidates (from the `plain_cc`
  grouping), since those are the groups it must classify.
- **Alert threshold:** chosen on **validation seeds 301–303** over the five
  accuracy scenarios, maximising mean ring-level F1 over the grid {0.2, 0.3,
  0.5, 0.7, 0.8, 0.9}. That is the proposed method's alert grid and objective
  (`experiments/tuning.py`). It has one tuned parameter where the proposed
  method has two (alert and edge threshold). The selected value is written to
  the results manifest.
- **Test:** E1's five scenarios × test seeds 1001–1010. Every stream digest
  must equal E1's for the same (scenario, seed). The proposed method's rows are
  re-run in the same session, on the same streams, for the pairing.

**Reported:** E1's columns (ring-level precision, recall, F1, user-level F1,
detection latency, alerts per hour), plus **node-level ROC-AUC** for both
methods. A node's score is the highest calibrated risk of any flagged ring
containing it, or 0. Its label is membership of any true ring. This node AUC
is labelled as **not comparable** to YelpChi, Amazon or Elliptic numbers in
the literature (different data, unit and labels).

**Comparison:** paired Wilcoxon signed-rank test of ring-level F1 per
scenario (10 pairs) and pooled (50 pairs), two-sided. The effect size is the
median of the paired differences and the matched-pairs rank-biserial
correlation. If `tabular_gb` beats the proposed method anywhere, that is
stated in the README and the paper.

**GraphSAGE (optional, `[gnn]`):** run only if time allows after E13 and E14,
under its own amendment written before its first run. Not running it is
reported as "not done", not as a negative result.

## E14: evasion-strength sweeps

**Question.** How does each method degrade as camouflage gets stronger?

**Strength knobs** (new simulator config `simulation.evasion_params`, which
overrides the per-mode strategy parameters for every ring using that mode;
absent means today's defaults, so existing streams are unchanged):
- `decoy_edges`: `decoys_per_action` ∈ {0, 1, 2, 4, 8} (default 2);
- `low_and_slow`: rate multiplier m ∈ {1, 2, 4, 8, 16}, applied as
  `action_mult = grow_mult = m` (default 8 and 6). The amount and hop-gap
  settings keep the mode's defaults;
- `identity_rotation`: `rotate_every` ∈ {0 (never), 12, 6, 3, 1} actions
  (default 3).

**Streams:** the `high_noise` scenario, with every random ring given the swept
mode (`random_rings.evasion_weights = {mode: 1}`) and the knob set as above.
Test seeds 1001–1010.

**Methods:** proposed, static Cypher cap 10, Louvain, and `tabular_gb`.
Configurations come from E1 and E13, unchanged. All methods see identical
streams per (mode, value, seed); the stream digests are recorded and checked.

**Reported per (mode, value, method):**
- recall over the rings using the swept mode;
- precision over all flags;
- ring-level F1;
- node-level AUC.

These are means with bootstrap 95% CIs over seeds. A paired Wilcoxon test
against the proposed method on the swept-mode recall, per (mode, value), uses
10 pairs, with the same effect sizes as E13.

## Provenance and reporting

- Results go in `results/e13_learned_baselines/` and
  `results/e14_evasion_strength/`, through the experiment harness. Every row
  carries run_id, scenario hash, method hash, seed and stream digest, and the
  manifest records the git commit and dirty state. A run from a dirty tree is
  repeated.
- Tables are generated from the CSVs into `docs/research/e13_tables.md` and
  `e14_tables.md`; findings and limitations go in `e13_e14_results.md`, written
  after the CSVs exist.

## Amendments

**1 (before any usable result): candidate groups are Louvain communities, not
connected components.** The first training run (manifest entry `e13_train`,
status `failed`) collected 42 candidate rows with 0 positives over all 60
training streams. The protocol's `plain_cc` grouping is degenerate. On every
scenario the weakly connected components merge almost every account into one
component, above the community detector's maximum size of 25, so nearly no
group is ever proposed. E1 shows the same: `plain_cc` flags 0 rings (recall
0.000) on every test stream. No learner can be trained on that.

`tabular_gb` therefore uses **Louvain communities** on the same projection
(E1's `louvain` grouping, sizes 3–25, seed 0), **with the density filter
switched off** (`min_density = 0`), so that the learned model, not a hand-set
density rule, decides which groups are rings. Everything else stands: the
same training protocol, threshold grid, objective, test seeds and comparisons.
