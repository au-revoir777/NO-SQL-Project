# Prompt 2: P1 (audit) and P2 (deliverables)

## P1. Audit

| Check | Result | Evidence / action |
|---|---|---|
| Every table and figure maps to one script and one config | **pass** for the original tables/figures (`make tables`, `make figures`; each generated table names its CSV and sha256); **pass** for revision tables (`scripts/make_refine_tables.py`; inputs named in each file header) | REPRODUCE.md §4 |
| REPRODUCE.md runs from a clean checkout | **partly verified**. A fresh clone plus `requirements-lock.txt` reproduced a recorded E5b run and an E1 row exactly (tests below). The full pipeline (about 20 h of experiments on the laptop) was not re-run end to end | `tests/test_reproducibility.py` |
| Dependencies pinned | **fail → fixed**. `pyproject.toml` had lower bounds only, and newer NumPy / scikit-learn / NetworkX change detection results on identical streams (seed 1002 E5b: F1 0.75 → 0.89). Added `requirements-lock.txt` (versions from the run manifests); CI installs with `-c requirements-lock.txt`; `requirements-w2.txt` for PyTorch / leidenalg. **Still open:** dev tools (pytest, hypothesis, fakeredis) are unpinned; no container image digest | lockfile, ci.yml |
| OS-specific behaviour | **noted**. Original runs on Windows 11, revision runs on Linux; identical results with the same library versions (verified on E1 and E5b rows). Timing differs by machine | §IV-E |
| Result rows record commit, seed, scenario hash, stream digest | **pass**. Rows carry `scenario_hash`, `seed`, `stream_digest`; `manifest.json` carries git commit, Python and library versions per grid | results/*/manifest.json |
| Trained scorer archived with training seeds and data hash | **pass**. `models/ring_scorer_lr.json` lists training and hold-out seeds, scenario hashes and per-run stream digests; W2 scorers have `results/w2_scorers/*.json` and the row CSVs; GraphSAGE has `results/w2_gnn/training.json` (seeds, digests, losses, torch version) | |
| Seed sets in config, not hard-coded | **partly**. Seed blocks are module constants in the experiment code (e.g. `TEST_SEEDS` in `w2_baselines.py`), declared in committed protocols, not in analysis scripts; analysis reads seeds from the CSVs. Moving them to `configs/seeds.yaml` would be cleaner | |
| Timing numbers: machine, load, warm-up, repeats | **partly**. Machine stated. "Experiments run one at a time" stated for the original. Warm-up: the first 10 simulated seconds are ingested before timing (scale runs). Repeats: 3 seeds (5 at 10k). The 3.5 h unfinished run is documented in `e5b_results.md`. Background load is not measured. Revision runs were concurrent and are not used for latency, except R5, re-run alone | §IV-E, Threats |
| Public data: sources, hashes, licences | **pass**. `docs/datasets.md` has sources, sha256 per file and a licence note; nothing redistributed | |
| Archive plan | **fail → planned**. No DOI release yet. Plan: a GitHub release of the camera-ready commit archived on Zenodo (VERIFY the GitHub–Zenodo integration for this account), cited with its DOI | Data and code availability paragraph |
| CI regenerates a table and compares | **pass**. `scripts/baseline_snapshot.py --check` regenerates the LaTeX tables byte-for-byte and hashes results and models. Updated snapshot `docs/audit/refine2_baseline.json` covers the revision evidence; CI now checks it | ci.yml |
| Determinism test | **added**. `test_detection_is_deterministic` reruns one seed twice; `test_recorded_e1_row_is_reproduced` compares with a recorded row under the locked versions (skipped otherwise). Hash-seed independence checked by hand (`PYTHONHASHSEED` 0–3 identical) | tests |

## P2. Deliverables

### Artifact checklist (conference artifact-appendix style)

- **Artifact:** repository `au-revoir777/NO-SQL-Project`, branch `feat/paper-refine` (camera-ready: a tagged release with a DOI, pending).
- **Contents:** simulator, scenarios (`configs/scenarios`), detectors, baselines (`detectors/external.py`), scorers and GraphSAGE model, all result CSVs with manifests, protocols (`docs/research/*_protocol.md`, committed before runs, with amendments), LaTeX source and generators.
- **Hardware:**
  - original: Intel i3-1115G4, 2 cores, 7.7 GB RAM, Windows 11;
  - revision: 2-core Linux container.
  - No GPU needed (GraphSAGE trains on CPU in about 19 min).
- **Software:** Python 3.11; `requirements-lock.txt`; `requirements-w2.txt` (PyTorch 2.5.1 CPU, leidenalg 0.12, igraph 1.0) for the W2 baselines; LaTeX with IEEEtran.
- **Time:**
  - each figure or table regenerates from CSVs in seconds;
  - re-running experiments: E1 about 10 min; R1 about 45 min; W2 tuning and evaluation about 6 h on 2 cores (GraphSAGE dominates); E5b at 10,000 accounts > 3.5 h for full recomputation.
- **Steps:** REPRODUCE.md §0–4, plus revision commands in each protocol and `scripts/make_refine_tables.py`.
- **Expected output:** byte-identical LaTeX tables from committed CSVs; identical result rows when experiments are re-run with the locked versions (verified for sampled rows); timings will differ.
- **Checks:** `pytest tests/test_reproducibility.py`; `python scripts/baseline_snapshot.py --check docs/audit/refine2_baseline.json`.

### "Data and code availability" paragraph

Added at the end of the paper (before the references): all data synthetic and generated by the code; repository contents; lockfile; regeneration scripts; test of a recorded run; latencies not reproducible by design; DOI archive at camera-ready.

### Not reproducible by design

- Wall-clock latencies and throughput (machine, load, OS, Docker).
- The Neo4j / Redis stack measurements (E8) depend on the Docker setup.
- Anything run with library versions other than the lock, where detection can change.
- GraphSAGE training is seeded (torch seed 0, CPU) and was run once. Bitwise reproducibility of PyTorch CPU training across machines is UNVERIFIED; the trained model file is committed, so evaluation does not depend on retraining.
