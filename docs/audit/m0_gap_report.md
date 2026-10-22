# M0 audit: gap report and baseline freeze

Milestone 0 of `master_prompt2.md`, run before P3 of the Phase 2 plan
(2026-10-22, branch `feat/m0-audit`, stacked on `feat/p2-auth` at `8656347`).
Each finding below was checked against the code, the result files or a test
run; a file merely existing was not taken as evidence.

## 1. Repository state

| Item | State |
|---|---|
| Branches | M1–M9 merged to `main` (PR #5 merged); not merged: `feat/p1-foundations` and `feat/p2-auth` (stacked on it). |
| Working tree | Clean except the owner's untracked `master_prompt2.md` (left untouched). |
| Tests | pytest 223 passed, 12 skipped (Neo4j/Redis integration tests; they run in CI's `integration-tests` job and passed there), Vitest 18, Playwright 5. CI run 39793233939 on `5bbc38f`: all 11 jobs green. |
| Paper numbers | All 6 generated files (`numbers.tex`, `tab1`–`tab4`) regenerate byte-identically from the committed CSVs (`scripts/baseline_snapshot.py`). |
| Frozen baseline | `docs/audit/m0_baseline.json`: SHA-256 and row count of all 28 files under `results/`, `models/` and `docs/paper/tables/`. CI now fails if any of them changes or a table stops regenerating (`baseline_snapshot.py --check`); new files are allowed. |

Headline numbers frozen by this snapshot (E1, 5 scenarios x 10 seeds, from
`results/e1_baselines/results.csv` via `numbers.tex`): proposed ring F1 0.73
(+/-0.05; P 0.76, R 0.74) vs. static cap 10 0.21, cap 100 0.19, Louvain 0.29,
connected components 0.00; a-priori thresholds 0.68. I recomputed the two
p-values the text states by hand: Wilcoxon p = 7.6e-10 vs. each static
baseline (text: p<0.001) and p = 0.034 tuned vs. a-priori (text: p=0.03). Both
are correct but typed, not generated (finding R6).

## 2. Findings by status

Legend: **V** implemented and verified (tests or reproduced output) ·
**T** implemented, insufficiently tested · **P** partial · **N** not
implemented · **B** blocked by environment or data.

### Simulator and graph layer

| Item | Status | Evidence / gap |
|---|---|---|
| Deterministic generation | V | Cross-process determinism test (M4); `stream_digest` per run in every result row. |
| Benign hubs, ring lifecycle, ring types | V | Simulator tests (M2); scenario hashes in manifests. |
| Adversarial knobs (evasion modes, decoys, rotation) | P | Modes exist and E1 has an `adversarial` scenario, but no *strength* sweep: E6 varies event rate, ring size and window only. Workstream E is open. |
| Event bus: in-memory and Redis Streams | T | Both implemented. Redis uses plain `XREAD` from `0-0`: no consumer groups, no acks, no idempotency key, so a restarted consumer re-reads the whole stream. The delivery semantics are undocumented (R2). |
| Neo4j and in-memory backends | V / P | Both tested (integration job). Every published latency number is in-memory only (Workstream A open). |

### Detection and scoring

| Item | Status | Evidence / gap |
|---|---|---|
| Static Cypher, hub-aware, cycle, smurfing, community, ensemble, hysteresis, incremental regions | V | Per-rule and property tests (M3, M9); E2 ablations. |
| Calibrated scoring | V | LR and HistGradientBoosting (`models/ring_scorer_{lr,gb}`) with **isotonic** calibration fitted on a later time slice. Only snapshot-level reliability is reported; ring-level calibration, precision@k by percentile and lift are missing (Workstream C). |
| Gradient-boosting scorer | P | It exists as a *scorer* option but was never evaluated as a baseline against the proposed pipeline under one protocol (Workstream D1). |
| Counterfactuals | P | Single-feature, logistic regression only (`counterfactual_value` returns `None` for GB). No feasibility constraints: it can propose impossible values, e.g. negative counts. Validity is tested on a few hand cases, never measured over alerts (Workstream B). |
| Evidence subgraphs | T | Produced. Fidelity against ground truth is not measured. |
| Early warning | P | `early_warnings_before_activation` counts **unique true rings** whose first early warning **or alert** came before activation. Two problems: (1) a tracked ring is matched to a true ring using the *final* members of both, which is look-ahead; (2) per-ring lead times are not stored, only the count. Fixing it needs a rerun with per-ring logging (Workstream F). |

### API, security and product

| Item | Status | Evidence / gap |
|---|---|---|
| `/api/v1` auth and roles | V | P2: 34 pytest + 5 Playwright tests, role matrix in `docs/webapp.md`. |
| **Legacy API routes** | **N (release-blocking)** | `/runs/start`, `/runs/inject`, `POST /config`, `/detectors/{type}`, `/rings/{id}/feedback`, `/oracle` (simulator ground truth!), `/graph` and the `/ws` WebSocket have **no authentication**, and CORS is `allow_origins=["*"]` (R1). |
| Request-size limits | N | None on any route. |
| Audit trail | P | Hash-chained and verifiable, but anyone who can write the file can rewrite the whole chain. There is no external anchor (signed checkpoint) and the threat model is undocumented. |
| Pseudonymization | N | No HMAC ingest layer (only HMAC use is the CSRF compare). |
| Web app pages | P | P1/P2 shell: login, users admin and system status are real. Alerts, cases, explorer, reports, experiments, simulator and rules are empty states (P3–P9). |
| Persistence | V | Alembic app DB (P1/P2). |

### Experiments, statistics and paper

| Item | Status | Evidence / gap |
|---|---|---|
| E1–E7 results | V | CSVs reproduce the paper tables exactly. |
| Run provenance | **P** | Manifests have scenario and method hashes, seeds and model SHA. Missing: git commit, start/end time, failure status and error details. **E4, E7 and `public/` have no manifest at all**, and the model path in manifests is an absolute Windows path (R3). |
| Confidence intervals | P | 95% CI over seeds in `stats.ci95`. E1 paired tests use 50 (scenario, seed) pairs as independent observations. The scenarios do differ, but the unit is undocumented in the paper (R5). |
| Multiple comparisons | N | 5 paired tests in E1 and 8 in E2 with no correction. E1 survives Holm easily (all p<1e-8 except 0.034, which also survives as the last step). Not yet checked for E2 (R5). |
| Hand-typed values in the paper | P | The two E1 p-values (correct, see above) and the environment facts (hardware, library versions) are typed by hand (R6). |
| Public data | V / B | AMLworld, Elliptic and AMLSim loaders and results. None of these datasets has device/card/IP sharing, so hub-aware detection cannot be validated on them (stated in the paper; keep). |

### CI and reproducibility

| Item | Status | Evidence / gap |
|---|---|---|
| Lint, types, unit, integration, smoke experiment, Docker build, web, contract, e2e | V | 11 jobs green. |
| Evidence immutability | V (new) | `baseline_snapshot.py --check` in `py-test`. |
| Secret scanning, dependency audit | N | Not in CI. Credentials were removed from the tree in `8656347`, but old commits still contain the former Neo4j and test passwords (owner to resolve in GitGuardian). |
| One command for all paper outputs | P | `make paper` regenerates figures and tables, but `numbers.tex` is not yet checked against every number used in the text (R6). |

## 3. Release-blocking and high-priority items

| # | Item | Fix in |
|---|---|---|
| R1 | Unauthenticated legacy routes, `/oracle` and `/ws`; CORS `*` | **Fixed** on `feat/r1-legacy-auth`: same role and CSRF dependencies as `/api/v1`, cookie-authenticated `/ws` with an Origin check, CORS from `CORS_ORIGINS`; 32 tests in `tests/test_legacy_auth.py` enumerate every route |
| R2 | Redis delivery semantics: at-least-once with idempotent processing, or documented replay-from-start | P10 (real-stack experiment) |
| R3 | Run manifests: git commit, timestamps, status/errors; manifests for E4, E7, public | **Fixed for new runs** on `feat/r3-provenance` (`experiments/provenance.py`, 4 tests). Existing results keep their original manifests and are frozen, not backfilled. |
| R4 | Early-warning look-ahead in member matching; per-ring lead times not stored | P10 (Workstream F) |
| R5 | Resampling unit documented; Holm correction applied | P10/P16 |
| R6 | Every number in the paper text from a generated macro | P16 |

## 4. Order of work (combined Phase 2 plan + master_prompt2)

1. **M0 audit** (this report) and **R1**: authenticate the legacy routes and the WebSocket, and restrict CORS.
2. **P10a** research metrics from existing artifacts: ring-level calibration, precision/lift@k%, alert burden. This needs R3 (provenance) first. Early warning needs a rerun (R4).
3. **P3–P9** analyst workflow.
4. **P10b–P12**: real-stack latency (needs Docker Desktop running), explanation quality, the GB baseline under the E1 protocol, then evasion-strength sweeps; GraphSAGE only if a fair protocol is feasible.
5. **P14–P16**: fault injection, secret scanning, pseudonymization if it fits, deployment, then the paper and final report.

Existing result files stay frozen (enforced by CI). New experiments write new directories.
