# Hub-Aware Incremental Fraud Ring Detection on Streaming Transaction Graphs

[![CI](https://github.com/au-revoir777/NO-SQL-Project/actions/workflows/ci.yml/badge.svg)](https://github.com/au-revoir777/NO-SQL-Project/actions/workflows/ci.yml)

BCSE406L - NoSQL Databases
Sanjay Kumar S (23BCE1248) · Roshan Parveen (23BCE1256)

This project started as a small Neo4j course model: planted fraud rings and
Cypher queries with a hard degree cap (see [Course baseline](#course-baseline)).
It is now a streaming research system with these parts:

- **Simulator:** a deterministic, real-time graph simulator. Legitimate users,
  benign hubs (office wifi, carrier NAT, family devices) and fraud rings that
  form, grow, mutate, evade and dissolve.
- **Detection:** an incremental engine that re-evaluates only the part of the
  graph each micro-batch touches, on Neo4j or an equivalent in-memory store.
- **Hub-aware weighting:** replaces the hard degree cap, so a ring hiding behind
  a busy hub can still be recovered while the hub's legitimate users are not
  flagged.
- **Explainable risk scoring:** a calibrated model gives every flag a reason,
  feature contributions, an evidence subgraph and a counterfactual.
- **Evaluation:** metrics against ground truth, structured logs, a
  tamper-evident audit trail and deterministic replay.

`master_prompt.md` is the specification. Milestone status is
[at the bottom](#milestone-status).

## Live dashboard

```bash
pip install -e ".[dev,redis]"
make demo              # builds web/ (Node 18+) and serves it with the API -> http://localhost:8000/ui/ (sign in: DEMO_* in .env)
make demo-docker       # or everything in containers: docker compose --profile app up --build
```

Without `make` (Windows): `cd web && npm ci && npm run build && cd ..`, then
`python -m fraudsim.cli api --port 8000`. A step-by-step guide, including a
five-minute walkthrough for presenting, is in [docs/HOWTO.md](docs/HOWTO.md).

The dashboard runs any scenario live: the transaction graph grows as events
arrive, rings form as red circles of transfers, and alerts pop into a queue
ranked by calibrated risk. Click a ring to see:
- why it was flagged;
- its feature contributions, counterfactual, evidence subgraph and timeline;
- confirm/dismiss buttons, which adapt the threshold and are audited.

From the controls you can inject any ring type or evasion on demand, switch
detectors, and retune the alert threshold and hub weighting live. The
*Oracle view* overlays the answer key: correct flags, false alarms and missed
rings. Details are in [`docs/dashboard.md`](docs/dashboard.md).

| Live run (demo_story, seed 7) | Oracle view |
|---|---|
| ![Dashboard](docs/images/dashboard_live.jpg) | ![Oracle view](docs/images/dashboard_oracle.jpg) |

![Ring drawer](docs/images/dashboard_oracle_drawer.jpg)

## Web app (Phase 2, in progress)

Phase 2 ([plan](docs/phase2/phase2_prompt.md)) builds a fraud-investigation web
app in `webapp/` (Next.js, TypeScript, Tailwind, shadcn/ui) on a versioned API
at `/api/v1`. P1 lays the foundations:
- the API contract, with request ids and a uniform error envelope;
- an app-state database (users, cases, notes, labels, rule sets, reports);
- the OpenAPI document and typed client;
- the app shell with a live system-status card.

P2 adds sign-in and roles:
- cookie sessions (JWT, argon2 passwords, CSRF, rate-limited login);
- analyst and admin roles, checked on the server for every route;
- a Users admin page (create, change role, deactivate; never delete);
- every login, logout and admin action written to the hash-chained audit trail.

Pages for later milestones say so instead of showing sample data. Details:
[docs/webapp.md](docs/webapp.md).

```bash
make db-upgrade                          # app-state DB (runs/app.db by default)
python -m fraudsim.cli create-user --email you@example.test --role admin   # prompts for a password
python -m fraudsim.cli api --port 8000   # API, incl. /api/v1 (set JWT_SECRET, see .env.example)
cd webapp && npm ci && npm run dev       # http://localhost:3000
make e2e                                 # Playwright (once: cd webapp && npm run e2e:install)
```

| Sign in | Users admin | Analyst opening an admin page (HTTP 403) |
|---|---|---|
| ![Login](docs/images/webapp_p2_login.png) | ![Users admin](docs/images/webapp_p2_users_admin.png) | ![403 page](docs/images/webapp_p2_forbidden.png) |

P3 adds the live dashboard: KPI cards, an alert feed and charts, streamed over SSE from the running engine (in-process, or Redis Streams with `REDIS_URL`).

![Live dashboard after a baseline run](docs/images/webapp_p3_dashboard.png)

P4 adds the Simulator page and replays:
- a scenario builder that the server validates exactly like the CLI;
- run controls and ring injection;
- a live Cytoscape graph;
- the story replay of `fraudsim demo-story`, ported to the app with deep links.

| Simulator during a demo_story run | Replay of run 00434da7845b at `?t=60&det=system&key=1` |
|---|---|
| ![Simulator](docs/images/webapp_p4_simulator.png) | ![Replay](docs/images/webapp_p4_replay.png) |

P5 adds alert triage and case management:
- an alert queue with filters, saved views, bulk actions and keyboard triage;
- alert pages with the evidence graph (and a table), contributions,
  counterfactuals, the ring timeline, labels that feed the alert policy, and
  versioned notes;
- cases with enforced transitions and frozen, hashed evidence;
- an admin audit view with the hash-chain check.

| Alert queue | Alert evidence |
|---|---|
| ![Alert queue](docs/images/webapp_p5_alerts.png) | ![Alert evidence](docs/images/webapp_p5_alert_evidence.png) |

| Escalated case | Audit view (admin) |
|---|---|
| ![Case](docs/images/webapp_p5_case.png) | ![Audit](docs/images/webapp_p5_audit.png) |

P6 adds the entity and graph explorer:
- search, with Ctrl+K from any page;
- entity pages for users, devices, cards and IPs;
- a k-hop neighbourhood graph that walks like the detector and shows where it
  stopped at a hub and why;
- pin and compare, and a ring view of membership over time.

It explores the current run, the course seed graph or a Neo4j database.

| Entity (course graph, `device_007`) | Walk stopped at the office-wifi hub | Ring over time |
|---|---|---|
| ![Entity](docs/images/webapp_p6_entity.png) | ![Hub stop](docs/images/webapp_p6_hub_stop.png) | ![Ring](docs/images/webapp_p6_ring.png) |

P7 adds investigation reports (HTML or PDF) for runs, cases and alerts:
- the evidence subgraph, contributions and counterfactuals per ring;
- the timeline and the analysts' notes;
- run metrics read from the run logs;
- a SAR-style summary;
- an optional Oracle comparison.

Every report is hashed and audited, and every page says "Generated from
simulated data for research/demo purposes. Not a regulatory filing."

| Report builder and list | Report, page 1 | Report, ring page |
|---|---|---|
| ![Reports](docs/images/webapp_p7_reports.png) | ![PDF page 1](docs/images/webapp_p7_report_pdf.png) | ![PDF ring page](docs/images/webapp_p7_report_ring.png) |

The P2–P7 screenshots are taken by `webapp/e2e/screenshots.spec.ts` against the
real API, with the e2e fixture accounts (`SCREENSHOTS=1 npx playwright test screenshots`).

| Dashboard (dark) | A page of a later milestone (light) |
|---|---|
| ![Web app dashboard](docs/images/webapp_p1_dashboard_dark.png) | ![Empty state](docs/images/webapp_p1_empty_state_light.png) |

| Mobile (375 px) | Mobile navigation |
|---|---|
| <img src="docs/images/webapp_p1_mobile.jpg" width="220" alt="Mobile dashboard"/> | <img src="docs/images/webapp_p1_mobile_nav.jpg" width="220" alt="Mobile navigation sheet"/> |

## Offline demo (story replay)

```bash
pip install -e ".[dev]"
make demo-story        # or: python -m fraudsim.cli demo-story --seed 7 --open
```

This writes `demo/story.html`, an offline, self-contained animated replay of a
real run. A ring hides behind a 44-account office wifi, and the same events go
through the original degree-capped Cypher rules (cap 10 and cap 100) and
through the hub-aware system. The page has:
- play/pause, speed, a scrubber and a detector switch;
- an *answer key* that marks correct flags, false alarms and misses;
- running scores, and alerts that pop up with their explanation at the batch
  where they fired.

Deep links jump to a moment, for example
`story.html#t=60&det=cap10&key=1`.

| Hub-aware system, end of run (answer key on) | Degree cap 10, end of run |
|---|---|
| ![Hub-aware](docs/images/demo_hubaware_t90.png) | ![Cap 10](docs/images/demo_cap10_t90.png) |

These screenshots are from run `00434da7845b` (seed 7), using the logistic
risk model trained on seeds 101–110. Over the same 2,512 events:

| Approach | Rings caught | False rings | Innocent users flagged |
|---|---|---|---|
| Rules, cap 10 | 2 / 3 | 23 | 52 |
| Rules, cap 100 | 2 / 3 | 24 | 74 |
| Hub-aware + risk model | 3 / 3 | 2 | 8 |

This is a single demonstration run. The cap rules reach the office ring only
through a coincidental 3-cycle among its members; the shared-IP query skips it
because of the cap. Multi-seed results are below.

## Results (Milestone 8)

All numbers come from `results/*/results.csv` (committed), produced by
`scripts/run_paper_experiments.py` on test seeds 1001+; thresholds were chosen
on separate validation seeds (`configs/tuned.json`). Every method sees the
identical event stream per scenario and seed. Commands: [REPRODUCE.md](REPRODUCE.md).

| 5 scenarios x 10 seeds | Ring precision | Ring recall | Ring F1 (mean, 95% CI) |
|---|---|---|---|
| **Hub-aware incremental (proposed)** | 0.76 | 0.74 | **0.73 ± 0.05** |
| Proposed, a-priori thresholds | 0.73 | 0.69 | 0.68 ± 0.05 |
| Louvain communities | 0.39 | 0.33 | 0.29 ± 0.06 |
| Static Cypher, cap 10 | 0.14 | 0.61 | 0.21 ± 0.05 |
| Static Cypher, cap 100 | 0.12 | 0.61 | 0.19 ± 0.05 |
| Connected components | - | 0.00 | 0.00 |

Every baseline is below the proposed method (paired Wilcoxon p < 0.001).

<p align="center">
  <img src="docs/paper/figures/fig1_pr_frontier.png" width="45%" alt="Precision/recall: degree cap vs hub weighting"/>
  <img src="docs/paper/figures/fig2_latency_scaling.png" width="45%" alt="Latency vs graph size"/>
</p>

- **Degree cap vs hub weighting** (left, shared-attribute rings only): no
  degree cap gets past recall 0.53 even with the scorer, while hub weighting
  with the scorer reaches 0.81. At low recall the cap with the scorer is the
  more precise, so the gain is reach, not dominance.
- **Scale** (right): full recomputation grows from 0.16 s per batch at 1,000
  users to 22.5 s at 100,000. The incremental dirty region stays below about
  2,000 users, so a batch takes 36 ms at 100,000 users. 10^6 users did not fit
  the 7.7 GB test laptop.
- **Ablations**: removing the calibrated scorer (F1 0.72 -> 0.39) or the
  hub-aware detector (-> 0.36) costs most. Incremental and full recomputation
  flag identical rings.
- **Limits**: rings that rotate identities or act low-and-slow evade every
  method tested. The positive results are synthetic.
- **Public data** (transaction rules only, no shared attributes in any public set):
  on a 4-day AMLworld slice the rules match none of the 55 laundering attempts
  inside it (account precision 0.03). Elliptic (acyclic, no amounts) and the
  AMLSim samples (cycles not time-ordered) give no flags. Details:
  [docs/datasets.md](docs/datasets.md).

Paper: [`docs/paper/paper.pdf`](docs/paper/paper.pdf) (IEEE conference
template; tables and the numbers in the text are generated, see `make tables`).

## Reproduce the paper results

```bash
python -m fraudsim.cli experiment --suite tune --output-dir results/   # thresholds on validation seeds -> configs/tuned.json
python scripts/run_paper_experiments.py                               # E1-E7 on test seeds -> results/*/results.csv
make tables figures                                                   # docs/paper/tables, docs/paper/figures
python scripts/make_architecture.py                                   # architecture.drawio -> .pdf/.png
make paper                                                            # docs/paper/paper.pdf (needs LaTeX)
```

[REPRODUCE.md](REPRODUCE.md) has the seeds, the run times and what each
experiment answers. Every result row carries its run id, scenario hash, method
hash and event-stream digest, every table carries the sha256 of its source
CSV, and CI regenerates the tables from the committed results and fails if they
differ.

## Architecture

![Architecture](docs/paper/figures/architecture.png)

The figure is generated from `docs/paper/figures/architecture.drawio`
(editable in draw.io) by `scripts/make_architecture.py`. Module-level view:

```mermaid
flowchart LR
  subgraph Simulator
    SC[Scenario YAML] --> GEN[EventGenerator<br/>benign users, hubs, ring agents,<br/>evasion, adaptive attacker]
    GEN --> GT[(Ground-truth ledger)]
  end
  GEN -->|events| PLAY[StreamPlayer<br/>rate · pause · speed]
  PLAY --> BUS[[Event bus<br/>asyncio / Redis Streams]]
  BUS --> ENG
  subgraph ENG[DetectionEngine - per micro-batch]
    ING[ingest] --> DIRTY[dirty set<br/>k-hop, hub-capped] --> VIEW[region view]
    VIEW --> HA[Hub-aware] & CY[Temporal cycle] & SM[Smurfing]
    FULL[timer: static Cypher Q1-Q4b,<br/>GDS Louvain/WCC] --> TR
    HA & CY & SM --> TR[Ensemble tracker<br/>stable ids, hysteresis]
    TR --> SCORE[Risk model + explanations<br/>early warning, alerts]
  end
  ING --> STORE[(Neo4j 5.26 + GDS<br/>or in-memory store)]
  STORE --> VIEW
  SCORE --> LOGS[events / detections / metrics logs<br/>hash-chained audit]
  SCORE --> API[FastAPI + WebSocket]
  SCORE -->|flags| GEN
  GT --> EVAL[Metrics vs ground truth]
  LOGS --> REPLAY[Deterministic replay]
```

| Package | Contents |
|---|---|
| `src/fraudsim/simulator/` | Config, world state, ring agents, event generator, stream player, recorder |
| `src/fraudsim/stream/` | Event bus (asyncio queue, Redis Streams) |
| `src/fraudsim/graph/` | Neo4j client, `GraphStore` contract, Neo4j and in-memory stores |
| `src/fraudsim/detectors/` | Detectors, ensemble/tracker, engine, closed-loop runner |
| `src/fraudsim/scoring/` | Features, calibrated scorer, explanations, early warning, training |
| `src/fraudsim/metrics/` | Evaluation vs ground truth, exporters (CSV/Parquet/Prometheus) |
| `src/fraudsim/logging/` | Run logs, audit trail, replay |
| `src/fraudsim/api/` | FastAPI app, live run, WebSocket |
| `src/fraudsim/demo/` | `demo-story` page builder |
| `src/fraudsim/experiments/` | Experiment harness, threshold tuning, suite (E1-E7), statistics, figures, LaTeX tables |
| `src/fraudsim/datasets/` | Loaders for IBM AMLworld, Elliptic, IBM AMLSim samples, PaySim |
| `web/` | Live dashboard (React, Vite, TypeScript, Cytoscape.js, Recharts) |
| `webapp/` | Phase 2 web app (Next.js App Router, TypeScript, Tailwind, shadcn/ui) |
| `src/fraudsim/api/v1/`, `src/fraudsim/appdb/` | Versioned API for the web app; app-state store (SQLAlchemy + Alembic) |
| `configs/scenarios/` | baseline, high_noise, hub_heavy, adversarial, scale_sweep, drift, demo_story |

Design notes are in [`docs/simulator.md`](docs/simulator.md),
[`docs/detection.md`](docs/detection.md), [`docs/scoring.md`](docs/scoring.md),
[`docs/metrics.md`](docs/metrics.md), [`docs/logging.md`](docs/logging.md) and
[`docs/dashboard.md`](docs/dashboard.md).

## Quick start

Requirements: Python 3.11, Node.js 18+ for the dashboard, and Docker Desktop
for Neo4j and Redis (the in-memory store works without Docker).

```bash
pip install -e ".[dev,redis]"
docker compose up -d                  # Neo4j 5.26 + GDS on 7474/7687, Redis on 6379
```

```bash
fraudsim simulate --scenario adversarial --seed 7            # stream + ground truth -> runs/<id>/
fraudsim detect   --scenario adversarial --seed 42           # simulate + detect + score + metrics + logs
fraudsim detect   --scenario scale_sweep --backend neo4j     # same on a live Neo4j
fraudsim replay   runs/<run_id>                              # re-run detection, must be identical
fraudsim audit-verify runs/<run_id>                          # check the audit hash chain
fraudsim compare-latency --scenario scale_sweep --seed 42    # incremental vs full recompute
fraudsim train-scorer --model logistic_regression            # (re)train the risk model
fraudsim run --scenario baseline --speed 10                  # live JSON event stream
fraudsim api                                                  # FastAPI on :8000, dashboard at /ui (after `make web`)
```

The commands above assume `pip install -e .`. Without installing, use
`PYTHONPATH=src python -m fraudsim.cli ...`.

Each `detect` run writes `runs/<run_id>/`:
- `events.jsonl`, `detections.jsonl`, `metrics.jsonl` and `errors.log`;
- `audit.jsonl`;
- `batches.jsonl` and `rings.jsonl`;
- `ground_truth*.jsonl`;
- `metrics/` (summary.json, CSV/Parquet tables, Prometheus text);
- `manifest.json` (seed, config hash, stream digest, model SHA-256).

## Tests

```bash
make test-unit                     # no services needed
pytest -m integration              # needs `docker compose up -d`
make lint
```

Besides unit tests for every detector on hand-built micro-graphs, there are
property tests for ring matching (`tests/test_properties.py`, hypothesis),
determinism and replay tests, and a headless 60-second scenario run that checks
the metrics it produces (`tests/test_headless_scenario.py`). The latest report
is `docs/reports/m9_test_report.txt`.

CI (GitHub Actions, `.github/workflows/ci.yml`) runs lint, unit tests, the
Neo4j/GDS and Redis integration tests against service containers, a one-seed
smoke experiment that regenerates tables and figures, a check that the
committed paper tables match the committed results, the dashboard build, and
the all-in-one Docker image.

## Milestone status

| Milestone | Status |
|---|---|
| M1 Architecture and repo layout | done (unsourced paper numbers replaced by placeholders) |
| M2 Real-time graph simulator | done |
| M3 Incremental detection engine | done |
| M4 Scoring and explainability (+ `demo-story`) | done |
| M5 Metrics | done |
| M6 Logging, audit and replay | done |
| M7 Live React dashboard | done |
| M8 Experiments, statistics, paper, public-data loaders | done (see Results above and `docs/paper/`) |
| M9 Quality bar (tests, CI, README, how-to) | done |

Phase 2 (web app and research extensions, [plan](docs/phase2/phase2_prompt.md)):

| Milestone | Status |
|---|---|
| P1 Foundations: `/api/v1` contract, app-state store, Next.js shell, CI | done |
| P2 Authentication and roles | done |
| M0 audit, R1 (legacy routes authenticated), R3 (run provenance) | done (`docs/audit/m0_gap_report.md`) |
| P10a/E10 ring-level calibration and alert utility; E11 early warning without look-ahead | done (`docs/research/`) |
| P3 Live dashboard (KPIs and alert feed over SSE) | done |
| P4 Simulator and replays | done |
| P5 Alerts and case management | done |
| P6 Entity and graph explorer | done |
| P7 Report generator | done |
| P8 Experiments and metrics page | next |
| P9–P16 | planned |

Known open items:
- Paper: check the bibliography entries against the publishers' pages before submission.
- Public data has no shared-attribute links, so hub-aware weighting is untested on real data (see [docs/datasets.md](docs/datasets.md)).

---

## Course baseline

The original course model is unchanged and still runs on its own. It is also
replayed by the new pipeline as `EventGenerator.generate_seed_events()`.

```bash
docker compose up -d neo4j
pip install -r requirements.txt
python seed.py
```

Set `NEO4J_PASSWORD` in `.env` first (`cp .env.example .env`; Compose refuses to start
without it). Then open http://localhost:7474 (user `neo4j`, your `NEO4J_PASSWORD`), and
paste queries from `queries.cypher` one block at a time. Setup help is in
[`SETUP.md`](SETUP.md), and the original plan is in
[`docs/PLAN.md`](docs/PLAN.md).

### Data model

```
(:User)-[:USED_DEVICE]->(:Device)
(:User)-[:HAS_CARD]->(:CreditCard)
(:User)-[:LOGGED_IN_FROM]->(:IPAddress)
(:User)-[:PERFORMED]->(:Transaction)-[:SENT_TO]->(:User)
```

30 users, 18 devices, 18 cards, 20 IPs, 40 transactions - 126 nodes. Small on
purpose: the whole graph fits on one screen, and because the rings are planted we
know exactly what each query should return.

The pools are wider than the user count on purpose. Sharing in the background
noise is capped at two users per device, card and IP, and noise transfers that
would close a loop are rejected. Without those caps, chance alone puts three
users on the same device and the accidental clusters look identical to a planted
ring. Every group of three or more in the results is deliberate.

### What is planted

| | Pattern | Expected result |
|---|---|---|
| Ring A | u01, u02, u03, u04 share `device_007` | found by Q1 |
| Ring B | u10, u11, u12 share `card_005` | found by Q2 |
| Cycle | u21 → u22 → u23 → u21 | found by Q3 |
| Ring C | u27, u28, u29 share `ip_004` | found by Q4a and Q4b |
| Hub | 12 users share `ip_001` | **not fraud** - office wifi |

Every user carries a `ring` property recording which planted ring it belongs to,
`null` for legitimate users. No detection query reads it - it exists only so the
results can be checked.

### The degree cap

`ip_001` is shared by twelve ordinary users. Any naive shared-attribute query
treats that as a twelve-member fraud ring.

Run Q4a (cap 100) and Q4b (cap 10) back to back. Same query, one number changed.
Q4a returns ring C plus twelve false positives; Q4b returns ring C alone.

The cost: a genuine ring hiding behind a busy node gets skipped too. Precision
bought with recall.

### Results (course baseline)

Screenshots from the Neo4j browser on the seeded graph.

#### The full graph (Q0)

126 nodes, 185 relationships.

![Full graph](images/q0-full-graph.png)

#### Shared device ring (Q1)

Four users on `device_007`.

![Shared device ring](images/q1-device-ring.png)

#### Shared card ring (Q2)

Three users on `card_005`.

![Shared card ring](images/q2-card-ring.png)

#### Circular money flow (Q3)

u21 to u22 to u23 and back.

![Money cycle](images/q3-money-cycle.png)

#### Degree cap off (Q4a)

Ring C found, plus twelve false positives from the shared office IP.

![No degree cap](images/q4a-no-cap.png)

#### Degree cap on (Q4b)

Same query, threshold changed from 100 to 10. False positives gone.

![Degree cap applied](images/q4b-with-cap.png)

#### Summary (Q5)

![Summary table](images/q5-summary.png)

---

### Measured result: the degree cap

Q4a and Q4b are the same query. The only difference is the degree threshold,
changed from 100 to 10. Measured in the Neo4j browser on the seeded graph:

| | Q4a (no cap) | Q4b (cap = 10) |
|---|---|---|
| Nodes returned | 17 | 4 |
| Users flagged | 15 | 3 |
| Of those, actually fraud | 3 | 3 |
| **Precision** | **20%** | **100%** |
| **Recall** | **100%** | **100%** |
| Query time | 302 ms | 74 ms |

Twelve of the fifteen users Q4a flags are innocent - they share `ip_001`, the
office wifi. The cap removes all twelve, and the query also runs about four
times faster because it stops expanding the hub node at all.

Recall stays at 100% here only because ring C sits behind a low-degree IP. That
is a property of this dataset, not a guarantee: a real ring hiding behind a busy
node would be skipped by the same rule that removes the false positives. The cap
buys precision and speed with recall, and the trade is the honest finding.
