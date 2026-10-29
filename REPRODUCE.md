# Reproducing the paper

Every table and figure in `docs/paper/` is generated from `results/*/results.csv`;
nothing is typed in by hand. This page lists the commands, in order.
(`make` targets are given where they exist; on Windows without `make`, run
the command shown next to it.)

## 0. Setup

```bash
python -m pip install -r requirements-lock.txt   # exact versions behind the recorded results
python -m pip install -e ".[dev]" --no-deps
```

Use the lock file to reproduce the tables: with newer library versions the event
streams are identical (same digest) but detection results can differ (for example
`e5b_large_hubs`, hub 500, seed 1002: F1 0.75 with the locked versions, 0.89 with
NumPy 2.5 / scikit-learn 1.9 / NetworkX 3.7).

Python 3.11, no database needed (all experiments use the in-memory graph store).
Neo4j (Docker) is only needed for `--backend neo4j` runs and the live demo's Neo4j mode.

## 1. Scorer (already trained, in `models/`)

```bash
python -m fraudsim.cli train-scorer --model logistic_regression --train-seeds 101-110 --test-seeds 201-205
```

## 2. Threshold selection on validation seeds 301-303

```bash
python -m fraudsim.cli experiment --suite tune --output-dir results/
```

Writes `results/tuning/results.csv` and `configs/tuned.json` (the selected
alert and edge thresholds, the whole grid of validation F1 scores, the seeds
and scenarios). The committed `configs/tuned.json` was produced this way.

## 3. Experiments on test seeds (1001+)

```bash
python scripts/run_paper_experiments.py          # all of them, in order
python scripts/run_paper_experiments.py frontier # or one
```

| Experiment | Output | Seeds | What it answers |
|---|---|---|---|
| `baselines` (E1) | `results/e1_baselines/` | 10 | accuracy and latency vs. static Cypher, Louvain, connected components |
| `ablations` (E2) | `results/e2_ablations/` | 5 | contribution of each component |
| `frontier` (E3) | `results/e3_frontier/` | 5 | degree cap vs. hub weighting on shared-attribute rings |
| `hub_size` (E5) | `results/e5_hub_size/` | 5 | recall of a ring hiding behind a growing hub |
| `sweeps` (E6) | `results/e6_sweeps/` | 5 | event rate, ring size, window length |
| `adaptivity` (E7) | `results/e7_adaptivity/` | 10 | adaptive attacker with vs. without detection feedback |
| `scale` (E4) | `results/e4_scale/` | 3 | per-batch latency, incremental vs. full, as the graph grows |

Every row carries `run_id`, `scenario_hash`, `method_hash` and `stream_digest`
(the digest of the exact event stream), so any number can be traced to a run
and re-run. `manifest.json` next to each CSV lists the methods' full configurations.

Since the M0 audit every run, including E4, E7 and `fraudsim public`, appends one
entry to `manifest.json` (`fraudsim.experiments.provenance`), also when it fails
or is interrupted. Each entry holds:
- `status` (`complete`, `failed`, `interrupted`) and `error` (type, message, traceback tail);
- `started_at` and `ended_at` (UTC), `wall_s`, and `rows` (rows this run added to `results.csv`);
- `git_commit` and `git_dirty`;
- Python, platform, CPU count and library versions;
- repo-relative paths with SHA-256 for models.

Results committed before this change keep their original manifests: E4, E7 and
`public/` have none, and the others lack these fields. They are frozen by
`docs/audit/m0_baseline.json`, not rewritten.
On the test laptop (Core i3-1115G4, 7.7 GB) the tuning grid took about 1.5 h (interrupted once and completed), the suite about 35 min, and the 100,000-user scale point another 30 min.

## 3b. Phase 2 research experiments (protocols in `docs/research/`)

Each has a protocol committed before its first result, and Markdown tables
generated from its CSVs (`docs/research/e*_tables.md`, never edited by hand).

```bash
# E10 ring-level calibration and alert utility (seeds 301-303 + 1001-1010)
python scripts/run_paper_experiments.py ring_alerts
python -m fraudsim.experiments.ring_calibration --results-dir results/ --report docs/research/e10_tables.md

# E11 early warning without look-ahead
python scripts/run_paper_experiments.py early_warning
python -m fraudsim.experiments.early_warning_eval --results-dir results/ --report docs/research/e11_tables.md

# E12 explanation quality: collect units, retrain a second scorer on seeds 111-120, analyse
python -m fraudsim.experiments.explanation_quality --collect --results-dir results
python -m fraudsim.cli train-scorer --model logistic_regression --train-seeds 111-120 \
    --test-seeds 201-205 --out results/e12_explanations/retrained_scorer_lr_seeds111-120.joblib
python -m fraudsim.experiments.explanation_quality --analyse --results-dir results \
    --retrained results/e12_explanations/retrained_scorer_lr_seeds111-120.joblib \
    --report docs/research/e12_tables.md

# E8 latency on the real stack. It WIPES the Neo4j database it is given, so use
# throwaway containers, not the one holding a demo graph:
docker run -d --name e8-neo4j -p 17687:7687 -e NEO4J_AUTH=neo4j/<random> neo4j:5.26-community
docker run -d --name e8-redis -p 16379:6379 redis:7.4-alpine
NEO4J_PASSWORD=<random> python -m fraudsim.experiments.stack_latency --run --results-dir results \
    --neo4j-uri bolt://localhost:17687 --redis-url redis://localhost:16379/0
python -m fraudsim.experiments.stack_latency --report docs/research/e8_tables.md
docker rm -f -v e8-neo4j e8-redis

# E13 learned baseline and E14 evasion strength (protocol docs/research/e13_e14_protocol.md)
python -m fraudsim.experiments.learned_baselines train   # GB on Louvain candidates, seeds 101-110
python -m fraudsim.experiments.learned_baselines tune    # alert threshold, seeds 301-303
python -m fraudsim.experiments.learned_baselines e13     # vs proposed, seeds 1001-1010
python -m fraudsim.experiments.learned_baselines e14     # evasion-strength sweeps
python -m fraudsim.experiments.learned_baselines report  # docs/research/e13_tables.md, e14_tables.md
```

On the test laptop: E13 training 2 min, tuning 5 min, E13 5 min, E14 14 min;
E12 collection 5 min, the second scorer about 25 min, the
analysis under a minute; E8 about 60 min.

## 4. Tables, figures, paper

```bash
make tables     # python -m fraudsim.experiments.latex_export --results-dir results/ --output-dir docs/paper/tables/
make figures    # python -m fraudsim.experiments.plotting --results-dir results/ --output-dir docs/paper/figures/
python scripts/make_architecture.py   # architecture.drawio -> architecture.pdf/.png
make paper      # pdflatex + bibtex in docs/paper/ -> paper.pdf
```

Each generated table starts with a comment naming the CSV it came from and that
file's sha256. `docs/paper/tables/numbers.tex` holds every number quoted in the
text as a LaTeX macro.

## 5. Public datasets (optional)

See [docs/datasets.md](docs/datasets.md).

```bash
python -m fraudsim.cli public --dataset amlworld
```

## Determinism

The simulator and the detectors are deterministic for a given scenario file and
seed: the same `stream_digest` and the same flagged rings come out on every run
(`tests/test_simulator.py` and `tests/test_detectors.py` check this, including across separate processes). Latency columns are
wall-clock measurements and vary with the machine and its load.

## GNN-inclusive pipeline (EvidGNN / EvidPipe / SagePipe) and round 3

The protocols are `docs/research/evidgnn_protocol.md` (including amendments 1–2) and `docs/research/round3_protocol.md`. Install the W2 extras (`requirements-w2.txt`, CPU PyTorch 2.5.1). All commands run from the repository root. Use `OMP_NUM_THREADS=1` (amendment 1: speed only).

```bash
E="python -m fraudsim.experiments.evidgnn"
$E train --fold all; $E train --fold A; $E train --fold B          # EvidGNN models
$E train --fold all --gate 0 --tag evidgnn_nogate                    # ablation A1
$E fused-train                                                       # EvidPipe scorer (out-of-fold)
$E train-sage-folds; $E fused-train --tag sage                       # SagePipe (amendment 2)
$E train-loso; python -m fraudsim.experiments.round3 gnn-loso        # H3 models
$E train-label                                                       # H4 models (10%, seed 7001)
for t in gnn-wide gnn-evidence evidgnn nogate evidpipe sagepipe; do $E tune $t; done
$E select                                                            # results/evidgnn_tuning/selected.json
$E test main      --methods evidpipe,gnn_unscored,evidgnn,gnn_scored,hybrid,proposed,rules   # 4001-4020
$E test ablation  --methods evidgnn,evidgnn_nogate,evidgnn_any,gnn_evidence,gnn_unscored,evidpipe,evidpipe_shipped_scorer
$E test loso; $E test label
$E test follow    --methods sagepipe,evidpipe,gnn_unscored,hybrid,proposed                    # 4801-4820
$E test overlap   --methods evidpipe,sagepipe,gnn_unscored,proposed,rules                     # 4701-4710
for s in capsweep step scorers loso decoy prcurve amount latency; do python -m fraudsim.experiments.round3 $s; done
python scripts/make_refine_tables.py                                 # tables and macros for the paper
```

`tests/test_reproducibility.py::test_recorded_evidpipe_row_is_reproduced` reruns one recorded EvidPipe row under the locked versions.

## AnchorPipe (docs/research/anchor_protocol.md)

```bash
A="python -m fraudsim.experiments.anchor"
$A reference; $A fused-train; $A tune; $A select; $A dev
for b in T1 T2 T3 T4; do $A test $b; done
python scripts/make_refine_tables.py        # Table VIII and macros
```

## Round 4: BWGNN comparator and guard controls (docs/research/round4_protocol.md)

```bash
R="python -m fraudsim.experiments.round4"
$R train-bwgnn; $R tune-bwgnn; $R select-bwgnn; $R test-bwgnn        # BWGNN vs AnchorPipe, seeds 6001-6020
$R trigger-ref                                                        # trigger thresholds on hold-out seeds 201-205
for b in S0 S1 S2 S3 S4 S5 S6; do $R guard $b; done                   # Table IX, seeds 6101-6165
$R traces                                                             # per-batch trigger traces
python scripts/make_refine_tables.py && python scripts/make_anchor_figures.py
python scripts/check_reproduction.py                                  # reruns 38 recorded Windows-era rows (Tables of baselines, scale, ablation)
sh scripts/make_anonymous_archive.sh anonymous_submission.zip         # double-blind archive
```
