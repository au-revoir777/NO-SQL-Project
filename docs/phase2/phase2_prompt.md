# ROLE
You are a senior full-stack engineer and applied-ML research engineer. Phase 1
(milestones M1–M9 of `master_prompt.md`) built a research-grade streaming
fraud-ring detector on Neo4j + Redis with a calibrated, explainable scorer, an
experiment harness and an IEEE-style paper. Phase 2 turns it into (1) a
professional fraud-investigation web application that analysts and admins can
actually use, and (2) a stronger paper, by adding the research items selected
in `docs/phase2/ANALYSIS.md`. Reuse the existing Python detection stack; do not
rewrite it.

Repo: https://github.com/au-revoir777/NO-SQL-Project
Read first: `master_prompt.md`, `README.md`, `REPRODUCE.md`, `SETUP.md`,
`docs/*.md`, `docs/phase2/ANALYSIS.md`, `docs/paper/sections/*.tex`,
`src/fraudsim/api/main.py`, `src/fraudsim/simulator/config.py`,
`src/fraudsim/scoring/explanations.py`, `src/fraudsim/demo/story.py`,
`web/src/`, `configs/scenarios/*.yaml`, `results/*/`, `Makefile`,
`docker-compose.yml`.

# GLOBAL RULES (apply to every milestone)
1. **No made-up numbers.** Every number in the UI, README, docs, PR bodies,
   tables, figures and the paper comes from an actual run or an existing file in
   `results/`, `runs/` or `docs/`, and is traceable to a run_id, config hash and
   seed (or to the file it was read from). The UI never shows hard-coded sample
   metrics; when data is missing it shows an empty state. Fixtures used in tests
   are labelled as fixtures and never shown as results. If a number cannot be
   produced, write "not measured" instead of estimating it.
2. **Never delete existing files.** Stale or superseded files are moved with
   `git mv` into `archive/` (keep the relative path, e.g. `archive/web-vite/`),
   and the move is listed in the PR body. Do not regress M1–M8: `make test-unit`,
   `make demo-story`, `make experiment`, `fraudsim replay` and the existing
   FastAPI routes and `/ws` must keep working until a milestone explicitly
   archives them with my go-ahead.
3. **Never push to `main`.** One feature branch per milestone, named
   `feat/p<N>-<slug>`, stacked: P1 branches from the M9 branch tip (or `main` if
   M9 is merged), P<N+1> branches from P<N>. Push with
   `git push -u origin <branch>`. Do not open PRs unless I ask; write each PR
   body to `demo/PR_BODY_P<N>.md` (summary, changes, how to test, test report
   excerpt, screenshots, files moved to `archive/`, known limitations).
4. **README on every push.** Update `README.md` before every push: milestone
   status table, new commands, new screenshots (real, from the running app),
   changed architecture. Keep the existing results sections intact unless a
   newer real run supersedes a number, in which case cite the new run.
5. **Step-by-step progress updates.** Before each task say what you are about
   to do; after it, say what changed (files), what you ran, and the result
   (pass/fail with output excerpt). Report failures as failures.
6. **Tests before commit.** Run lint, type checks and the relevant test suites
   before every commit; fix failures before moving on. Save each milestone's
   test output to `docs/reports/p<N>_test_report.txt`.
7. **State assumptions** instead of asking, unless blocked. Mark them
   `ASSUMPTION:` in the plan and PR body. Verify any external service limit
   (free tiers, plugin support) from its official docs before relying on it,
   and cite the doc URL in `docs/deploy.md`.
8. **Pinned versions.** Pin exact versions in `package.json` (no `^`/`~`),
   `pyproject.toml` extras and Docker images. Record them in
   `docs/webapp.md`.
9. **Security basics.** No secrets in git (`.env.example` only), passwords
   hashed with argon2, httpOnly + Secure + SameSite cookies, CSRF protection on
   state-changing requests, server-side role checks on every protected route
   (never rely on the UI hiding a button), input validation with pydantic
   (server) and zod (client), rate-limited login.
10. **Synthetic-data honesty in the product.** The app runs on simulator data
    and public research datasets. Ground-truth-based metrics (precision, recall,
    "missed rings") are shown only in Oracle mode, labelled "Oracle (simulator
    ground truth)". Reports carry a footer: "Generated from simulated data for
    research/demo purposes. Not a regulatory filing."
11. **Commit messages**: `feat(p<N>): …`, `test(p<N>): …`, `docs(p<N>): …`.
    Commit per coherent step, not one giant commit.

# EXISTING STATE (do not regress)
- Python 3.11 package `src/fraudsim/` (simulator, stream, graph, detectors,
  scoring, metrics, logging, api, demo, experiments, datasets), CLI `fraudsim`.
- FastAPI app `src/fraudsim/api/main.py`: `/health`, `/status`,
  `/runs/{start,pause,resume,stop,speed,rate,inject}`, `/scenarios`,
  `/catalog`, `/detectors`, `/config`, `/graph`, `/oracle`, `/events/recent`,
  `/rings`, `/rings/{id}`, `/rings/{id}/feedback`, `/metrics/summary`,
  `/metrics` (Prometheus), `/ws`, dashboard at `/ui`.
- Vite + React + Cytoscape + Recharts dashboard in `web/` (7 components).
- Offline replay `demo/story.html` built by `fraudsim demo-story`, data in
  `demo/story_<run_id>.json`, deep links `#t=…&det=…&key=…`.
- Results: `results/e1_baselines … e7_adaptivity`, `results/public`,
  `results/tuning`, generated macros `docs/paper/tables/numbers.tex`.
- Services: Neo4j 5.26 community + GDS plugin, Redis 7.4 (`docker-compose.yml`).
- Explanations per ring: contributions, reason text, evidence subgraph JSON,
  counterfactuals, calibration bucket (`src/fraudsim/scoring/explanations.py`).
- Analyst feedback `AlertPolicy` (`docs/scoring.md`), hash-chained audit log,
  deterministic replay.

# TARGET ARCHITECTURE
```
webapp/  (Next.js App Router, TypeScript strict, Tailwind, shadcn/ui)
   │  server components + route handlers (BFF proxy, cookie auth)
   ▼
FastAPI  src/fraudsim/api/  ── new versioned router /api/v1/* (existing routes untouched)
   ├── detection engine, simulator, scorer, explanations (existing code)
   ├── app-state store (SQLAlchemy 2 + Alembic: users, cases, notes, labels,
   │   rule-set versions, report records). SQLite by default, Postgres via URL.
   ├── Neo4j (detection graph, entity explorer queries)
   └── Redis (Streams: events, alerts, metrics → SSE fan-out; rate limits)
```
ASSUMPTION: app state (cases, users) lives in a relational store rather than in
Neo4j so that TTL pruning of the detection graph can never delete analyst work,
and so tests run without services. Revisit in P1 if you find a reason against.

# DESIGN SYSTEM (applies to all UI milestones)
- **Foundation:** shadcn/ui (new-york style) on Tailwind; CSS variables for
  every colour; light and dark themes via `next-themes` (system default, toggle
  in header). No hard-coded hex values in components.
- **Typography:** Geist Sans for UI, Geist Mono for ids, hashes, amounts and
  code (via `next/font`). Scale: 12 / 14 (body) / 16 / 20 / 24 / 30 px;
  tabular numerals (`font-variant-numeric: tabular-nums`) in tables and KPIs.
  Sentence case for labels and headings.
- **Colour tokens:** shadcn neutrals (`background`, `foreground`, `card`,
  `muted`, `border`, `primary`, `destructive`, `ring`) plus domain tokens
  carried over from `web/src/index.css` so screenshots stay consistent:
  `--risk-alert` (#d1453b / dark #ef6a5f), `--risk-confirmed` (#e07b16 /
  #f29a3c), `--risk-candidate` (#c9a215 / #dfc04a), `--benign` (#b3b7bd /
  #5a6068), `--node-device` (#7a5cc7 / #a38bec), `--node-card` (#1f9a92 /
  #3cc2b8), `--node-ip` (#3d6fd6 / #6e98ef), `--node-hub` (#2850a8 / #8fb0ff),
  `--ok` (#2f8f5b / #4fc283), `--warn` (#c98a12 / #e5a93a). Chart series use
  shadcn `--chart-1..5`. Check every text/background pair for WCAG AA contrast
  and adjust the token, not the component.
- **Never colour only:** risk and status always pair colour with a text label
  or icon (lucide-react); graph node types also differ by shape.
- **Layout:** shadcn `Sidebar` (collapsible to icons, 16rem expanded) with
  groups Monitor (Dashboard, Alerts, Cases), Investigate (Explorer, Reports),
  Simulate (Simulator, Replays), Research (Experiments), Admin (Rules, Users,
  Audit). Header: breadcrumb, command-palette trigger (⌘K / Ctrl+K), live
  connection indicator, theme toggle, user menu. Content: max-width 1440px,
  24px page padding (16px on mobile), 8px spacing grid, cards with 12px radius.
  Responsive down to 375px width; the sidebar becomes a `Sheet` on mobile.
- **Data density:** tables 40px rows, sticky headers, column visibility,
  sorting, filtering, pagination, row selection; numbers right-aligned.
- **States:** every data view has explicit loading (shadcn `Skeleton` shaped
  like the content), empty (icon, one sentence, primary action, e.g. "No alerts
  yet. Start a simulation"), error (`Alert` destructive with message, request
  id and Retry) and stale/disconnected (banner when the live stream drops, with
  auto-reconnect and backoff). Toasts via `sonner` for actions, never for
  errors that need reading.
- **Motion:** 150–200 ms ease-out; respect `prefers-reduced-motion` (graph
  animation and replay transitions switch to instant).
- **Accessibility:** WCAG 2.2 AA; keyboard reachable everything; visible focus
  ring; `aria-live="polite"` region announcing new alerts (throttled); graph
  views have a tabular alternative (members/edges list).
- **Components to use:** `sidebar`, `data-table` (TanStack Table), `card`,
  `chart` (shadcn charts on Recharts), `dialog`, `alert-dialog`, `sheet`,
  `tabs`, `form` (react-hook-form + zod), `input`, `textarea`, `select`,
  `combobox` (popover + command), `slider`, `switch`, `checkbox`,
  `radio-group`, `toggle-group`, `calendar` + date-range picker, `badge`,
  `button`, `dropdown-menu`, `context-menu`, `tooltip`, `hover-card`,
  `popover`, `command` (command palette), `sonner`, `skeleton`, `alert`,
  `breadcrumb`, `avatar`, `separator`, `scroll-area`, `resizable`,
  `progress`, `pagination`, `accordion`.
- **Graph rendering:** Cytoscape.js (already used in `web/`) loaded with
  `next/dynamic` (`ssr: false`), `fcose` layout for explorer/ring views,
  `preset` layout for replay frames; level-of-detail and a node cap for large
  graphs as in M7. Styling reads the CSS tokens above.
- **Server state:** TanStack Query; typed client generated from the OpenAPI
  schema (`openapi-typescript` + `openapi-fetch`).

---

# MILESTONE P1: Foundations — monorepo, API v1 contract, app-state store, CI
Goal: a running skeleton end to end, with a typed contract between the Next.js
app and FastAPI, and CI from day one.
Tasks:
- Create `webapp/` (Next.js App Router, TypeScript strict, ESLint, Prettier,
  Tailwind, shadcn/ui init, `next-themes`, Geist fonts, TanStack Query).
  Keep `web/` (Vite) untouched and working.
- Add `src/fraudsim/api/v1/` router mounted at `/api/v1`, with sub-routers
  `auth`, `runs`, `alerts`, `cases`, `entities`, `graph`, `reports`,
  `experiments`, `rules`, `stream`, `admin`. Pydantic v2 schemas in
  `src/fraudsim/api/v1/schemas/`. Uniform error envelope
  `{error: {code, message, request_id}}`, request-id middleware, pagination
  envelope `{items, next_cursor, total}`.
- App-state store: SQLAlchemy 2 models + Alembic migrations for `users`,
  `cases`, `case_alerts`, `notes`, `labels`, `rule_sets`, `reports`,
  `audit_refs`; `DATABASE_URL` (default `sqlite:///runs/app.db`).
- Export OpenAPI to `docs/api/openapi.json` (`make openapi`); generate
  `webapp/src/lib/api/schema.d.ts` (`make api-types`).
- Makefile targets: `webapp-dev`, `webapp-build`, `webapp-test`, `e2e`,
  `openapi`, `api-types`, `stack-up` (full compose).
- GitHub Actions `.github/workflows/ci.yml` (extend the M9 workflow if it
  exists, do not replace it): jobs `py-lint` (ruff, mypy), `py-test`
  (`make test-unit`), `web-lint` (eslint, `tsc --noEmit`), `web-test`
  (Vitest), `web-build` (`next build`), `contract` (regenerate OpenAPI and fail
  on diff). Cache pip and npm.
- `docs/webapp.md`: architecture, versions, how to run.
Deliverables: skeleton app with sidebar layout and theme toggle rendering a
`/health`-backed status card; OpenAPI file; migrations; CI workflow.
Acceptance criteria / tests:
- `pytest` passes, including new tests for the error envelope, request id and a
  migration up/down round trip on SQLite.
- Contract test: committed `docs/api/openapi.json` equals the generated one.
- Vitest renders the layout; `next build` succeeds with zero type errors.
- Existing `make test-unit` and `make demo` still pass.
**STOP and wait for my go-ahead.**

# MILESTONE P2: Authentication and roles (analyst, admin)
Goal: simple, safe role-based access.
Tasks:
- `POST /api/v1/auth/login`, `/logout`, `GET /me`; JWT in an httpOnly,
  Secure, SameSite=Lax cookie (short expiry + refresh), CSRF double-submit
  token for POST/PUT/PATCH/DELETE, argon2 password hashing, login rate limit
  (Redis, in-memory fallback).
- Roles: `analyst` (view, triage, cases, notes, labels, reports, run
  simulations) and `admin` (all analyst rights + rules/thresholds, users,
  audit view, detector toggles, data reset). Enforce with a FastAPI dependency
  on every v1 route; matrix documented in `docs/webapp.md`.
- `fraudsim create-user --role admin` CLI; demo accounts seeded only from env
  vars (`DEMO_ADMIN_EMAIL/PASSWORD`, `DEMO_ANALYST_EMAIL/PASSWORD`), never
  committed.
- Next.js: `/login` page (form + zod), middleware redirect for protected
  routes, role-aware sidebar, user menu with logout; a BFF route handler that
  forwards cookies to FastAPI.
- Every login, logout and role-protected action is written to the existing
  audit trail (`src/fraudsim/logging/audit.py`).
Deliverables: login flow, role guards, user admin page (admin only: list,
create, deactivate, change role — deactivate, never hard delete).
Acceptance criteria / tests:
- pytest: wrong password, locked-out rate limit, expired token, CSRF missing,
  analyst forbidden from admin routes (403) for every admin endpoint
  (parametrised over the router).
- Playwright: login as analyst → admin pages hidden and direct URL returns 403
  page; login as admin → rules page visible.
**STOP and wait for my go-ahead.**

# MILESTONE P3: Live dashboard (KPIs + alert feed over SSE from Redis Streams)
Goal: an at-a-glance live monitor.
Tasks:
- Publish engine outputs to Redis Streams `fraudsim:alerts`,
  `fraudsim:metrics`, `fraudsim:events` (MAXLEN-trimmed) through the existing
  event bus; in-process fallback when `REDIS_URL` is unset.
- `GET /api/v1/stream/alerts` and `/stream/metrics` as Server-Sent Events:
  `XREAD BLOCK` from the client's `Last-Event-ID` so reconnects resume without
  gaps; heartbeat comments every 15 s. Keep `/ws` for the old dashboard.
- Dashboard page: KPI cards (events/s, graph size, open alerts, alerts/hour,
  rings tracked by status, detect latency p50/p95/p99 from the latency
  module), each with sparkline; Oracle-only cards (ring precision/recall/F1,
  missed rings) behind a toggle with the label from Global Rule 10; live alert
  feed (risk badge, ring type, members count, top reason, age; click opens
  alert detail); latency and throughput charts; connection indicator.
- Throttle UI updates (≤4 renders/s); `aria-live` announcement of new
  high-risk alerts.
Deliverables: dashboard page, SSE endpoints, Redis publisher.
Acceptance criteria / tests:
- pytest (integration, Redis): SSE delivers alerts in order and resumes from
  `Last-Event-ID` after a forced disconnect with no loss or duplicates.
- Vitest: KPI card loading/empty/error states.
- Playwright: start a `baseline` run (seed fixed) → at least one alert appears
  in the feed; values shown equal `GET /api/v1/runs/current/metrics`.
- Every KPI on the page is traceable to the run_id shown in the header.
**STOP and wait for my go-ahead.**

# MILESTONE P4: Simulator page (configure, run, live graph, replay)
Goal: configure and run fraud-ring scenarios from the browser, and port the
animated `story.html` replay.
Tasks:
- Scenario builder form generated from `SimulationConfig`
  (`src/fraudsim/simulator/config.py`): duration_seconds, target_event_rate,
  num_users/devices/cards/ips, heavy_tail_alpha, user_join_rate,
  user_leave_rate, amount_median, amount_sigma, hubs (name, kind, size,
  category, fill/start time), hub_distribution (count, min/max size, alpha,
  categories), drift (trigger time, new hub size/kind, shift multiplier),
  rings list (ring_id, ring_type ∈ RingType, size, spawn_time_s, evasion ∈
  EvasionMode, shared_attribute, length, grow_interval_s, initial_members,
  active_duration_s, action_interval_s, mutate_prob, intensity), random_rings,
  adaptive attacker (penalty, respawn delay, max rings, strategies), seed.
  zod schema mirrors the pydantic one; server validates with the existing
  scenario loader. Presets load from `configs/scenarios/*.yaml`; "Save as
  YAML" downloads, admin can save to `configs/scenarios/custom/`.
- Controls: start, pause, resume, stop, speed, rate, inject ring (type +
  evasion), detector toggles (admin), via `/api/v1/runs/*` wrapping the
  existing live run.
- Live graph (Cytoscape): users/devices/cards/IPs/transactions styled by type
  token and shape, rings highlighted by status, hubs sized by degree, windowed
  view + node cap; Oracle overlay (TP/FP/missed) off by default; export
  PNG/SVG.
- Replays: list recorded runs (`runs/*/manifest.json`, `demo/story_*.json`);
  replay page reproduces `story.html`: play/pause, speed, scrubber, detector
  switch (cap10 / cap100 / hub-aware), answer key, running scores, alerts
  popping at their batch, deep links `?t=&det=&key=` (also accept the old
  `#t=…` form). Data comes from `GET /api/v1/replays/{run_id}` returning the
  same JSON `fraudsim demo-story` writes. Keep `demo/story.html` as is.
Deliverables: simulator page, replay page, `/api/v1/replays`.
Acceptance criteria / tests:
- pytest: invalid configs rejected with field-level errors; a config built in
  the form round-trips to YAML and loads with the scenario loader to the same
  config hash.
- Determinism: starting seed 7 `demo_story` from the UI produces the same
  stream digest as `fraudsim demo-story --seed 7`.
- Playwright: replay of run `00434da7845b` at `?t=90&det=cap10&key=1` shows the
  same counts as the end of `demo/story.html` for that detector (read both from
  the JSON, do not hard-code).
- axe: no serious/critical violations on simulator and replay pages.
**STOP and wait for my go-ahead.**

# MILESTONE P5: Alerts and case management
Goal: a triage queue and investigation workflow with evidence and feedback.
Tasks:
- Alerts table (data-table): risk, calibrated bucket, ring type, members,
  detectors, first/last seen, status (new, triaged, escalated, closed),
  assignee; filters (risk range, type, status, detector, time range), saved
  views, bulk assign/close, keyboard navigation (j/k, Enter).
- Alert detail page (tabs): Overview (score, calibration bucket with observed
  rate, plain-English reason), Evidence (evidence subgraph in Cytoscape + a
  table alternative, member list with links to the explorer), Contributions
  (bar chart of per-feature contributions), Counterfactuals (existing
  sentences; interactive what-if panel added in P11), Timeline (ring events
  and status changes from the tracker and audit log), Activity (notes,
  assignments, labels).
- Cases: create from one or more alerts, assign, status (open, in review,
  escalated, closed with resolution), priority, notes (markdown, edit
  history kept), attachments of evidence snapshots (frozen JSON copy of the
  evidence subgraph at time of attach, hashed into the audit log).
- Analyst feedback labels on alerts: `confirmed_fraud`, `dismissed_benign`,
  `needs_info`; confirm/dismiss calls the existing `AlertPolicy` through
  `/rings/{id}/feedback` logic; show the threshold adaptation returned.
- Everything writes to the audit trail; `fraudsim audit-verify` must still
  pass.
Deliverables: alerts list, alert detail, cases list/detail, notes, labels.
Acceptance criteria / tests:
- pytest: state machine of case statuses (invalid transitions rejected),
  feedback updates thresholds exactly as `AlertPolicy` defines, audit chain
  verifies after a scripted triage session.
- Vitest: data-table filters and bulk actions; form validation.
- Playwright: analyst opens an alert, adds a note, labels it, creates a case,
  escalates it; admin sees it in the audit view.
**STOP and wait for my go-ahead.**

# MILESTONE P6: Entity and graph explorer
Goal: investigate any account, device, card or IP.
Tasks:
- Search (command palette and page): by id prefix across User, Device,
  CreditCard, IPAddress (Neo4j indexes; in-memory store equivalent), with
  type filter.
- Entity page: attributes, degree, hub weight (for attributes), linked alerts
  and rings, activity timeline, transactions in/out with amounts.
- k-hop neighbourhood view (k = 1..3) with the same hub-capped expansion the
  detector uses (show where expansion stopped at a hub and why), edge weights
  from the hub-aware weighting, filters by relationship type and time window,
  expand-on-click, "pin and compare" two entities, export PNG/SVG and JSON.
- Ring view: all members and shared attributes of a tracked ring over time
  (grow/shrink/merge/split from the tracker).
Deliverables: explorer pages, `/api/v1/entities/*`, `/api/v1/graph/neighbourhood`.
Acceptance criteria / tests:
- pytest on hand-built micro-graphs (reuse `tests/conftest.py` patterns): the
  k-hop endpoint returns exactly the expected nodes/edges and stops at hubs as
  the detector's dirty-set expansion does.
- Integration (Neo4j): same answers as the in-memory store for a seeded graph.
- Playwright: search `device_007` on the course seed graph → four users
  (Ring A in README), matching the README table.
**STOP and wait for my go-ahead.**

# MILESTONE P7: Report generator (investigation report + SAR-style summary)
Goal: downloadable, evidence-backed reports.
Tasks:
- Report builder (form): scope = time range and/or scenario run and/or
  selected alerts/cases; sections to include (executive summary, alert table,
  per-ring detail with evidence subgraph image, contributions chart,
  counterfactuals, timeline, analyst notes, metrics for the run, Oracle
  comparison if enabled); format HTML or PDF.
- Server-side rendering: Jinja2 HTML template (print CSS, IEEE-neutral
  styling, page numbers), charts as static SVG generated server-side
  (matplotlib, reusing `src/fraudsim/experiments/plotting.py` style), graph
  snapshots via Cytoscape export captured during report build. PDF via
  Playwright Chromium print (ASSUMPTION: avoids WeasyPrint native deps on
  Windows; verify in P1 and record the choice).
- SAR-style summary section: subject entities, activity summary, amounts and
  dates, typology (ring type, evasion), evidence references, analyst
  narrative (from notes); fixed disclaimer from Global Rule 10.
- Each report gets an id, the run_ids and config hashes it used, a SHA-256 of
  the file, and an audit entry; reports list page with re-download.
Deliverables: report builder, report list, `/api/v1/reports/*`, templates.
Acceptance criteria / tests:
- pytest: report numbers equal the values from the underlying run logs
  (compute both, compare); the report manifest lists every run_id used; hash
  recorded in audit.
- Golden test: HTML report for a fixed seed is byte-stable apart from the
  timestamp field.
- Playwright: generate a PDF for a case and download it (non-empty, correct
  content-type).
**STOP and wait for my go-ahead.**

# MILESTONE P8: Experiments and metrics page (real experiment outputs only)
Goal: browse the paper's evidence in the app.
Tasks:
- `GET /api/v1/experiments` lists `results/*/` (manifest.json + results.csv);
  `/experiments/{id}` returns rows, column docs and summaries computed with
  the existing `src/fraudsim/experiments/stats.py` (mean, 95% CI, paired
  Wilcoxon) — no new aggregation logic.
- Pages: overview (table of experiments with run counts, seeds, config hash,
  CSV sha256), E1 baselines table and per-scenario view, E3 frontier chart,
  E4 scale chart, E2 ablation table, evasion recall chart, public-data table,
  links to `docs/paper/paper.pdf` and figure PDFs; download CSV; "how to
  reproduce" command copied from `REPRODUCE.md`.
- Every chart shows its source file and row count in a caption.
Deliverables: experiments pages and endpoints.
Acceptance criteria / tests:
- Consistency test: for every macro in `docs/paper/tables/numbers.tex` that has
  an API equivalent (at least `\EPropF`, `\ECapTenF`, `\ELouvainF`,
  `\ScaleIncMs`, `\ScaleFullMs`), the API value rounded the same way equals
  the macro. This guards against drift between paper and app.
- Empty state when `results/` is absent (fresh clone without results).
**STOP and wait for my go-ahead.**

# MILESTONE P9: Rule and threshold configuration (admin)
Goal: safe, versioned, audited configuration.
Tasks:
- Versioned `RuleSet`: alert threshold per ring type, hub-aware edge
  threshold θe, hub-weight parameters, time-decay half-life, window length,
  dirty-set k and fan-out limits, hysteresis settings, detector enable flags,
  static-Cypher degree cap, early-warning threshold. Defaults read from the
  current configs (`configs/tuned.json` and detector config objects).
- Form with zod + pydantic validation and ranges, diff view against the active
  version, "apply live" (wraps the existing `POST /config`), rollback to any
  version, change reason required; every change audited.
- "Dry run": replay a recorded run with the candidate rule set and show the
  difference in alerts (counts and list) before applying — uses the existing
  replay code path.
Deliverables: rules page, `/api/v1/rules/*`.
Acceptance criteria / tests:
- pytest: invalid values rejected; apply → engine uses new values on next
  batch; rollback restores the exact previous config hash; dry run on a fixed
  run is deterministic.
- Playwright: analyst cannot open the page; admin changes θe, sees a dry-run
  diff, applies, and the audit view shows the change with reason.
**STOP and wait for my go-ahead.**

# MILESTONE P10: Research A1 + A3 + A6 — real-stack latency, ring-level calibration, early warning
Goal: close the latency and calibration threats and report early warnings
(see `docs/phase2/ANALYSIS.md` §(c) A1, A3, A6).
Tasks:
- E8 `stack_latency`: E4 users sweep and a shortened E1 on
  `--backend neo4j` with the Redis Streams bus; measure ingest→write,
  per-batch detect, event→flag p50/p95/p99, consumer lag, events/s; sweep
  Redis consumer batch count and block timeout (motivated by HYADES,
  `bora2026hyades`). Exclude and report JVM warm-up. Verify identical flagged
  rings vs in-memory on the same seeds (stream digest + ring sets).
- E9 `calibration`: ring-level reliability diagram, Brier and ECE at alert
  level, Precision@k and Lift@k (k = 1%, 5%, 10% of alerts), Platt vs isotonic
  on the same splits (motivated by `azbergen2026calibration`,
  `ding2021temperature`).
- Early warning: lead-time distribution and precision of early warnings from
  existing E1 logs (`early_warnings_before_activation` column and run logs).
- New figures/tables via the existing plotting and LaTeX export; new macros
  appended to `numbers.tex` by `make tables`.
- Surface the new results on the Experiments page.
Deliverables: `results/e8_stack_latency/`, `results/e9_calibration/`,
early-warning table, figures, macros, `REPRODUCE.md` commands.
Acceptance criteria / tests:
- Each result row has run_id, config hash, seed, stream digest; manifests
  written; `make tables` regenerates macros without manual edits.
- Unit tests for Lift@k, ring-level ECE and lead-time computation on
  hand-made inputs with known answers.
- No number appears in docs before its CSV exists.
**STOP and wait for my go-ahead.**

# MILESTONE P11: Research A2 — explanation quality + interactive what-if
Goal: answer the specification's RQ4 (explanation quality) with measurements.
Tasks:
- E10 `explanations` over E1 test seeds: counterfactual validity (apply change,
  re-score, crosses threshold?), stability under small perturbations of
  non-actionable features (after `artelt2021robustness`), consistency after
  retraining the scorer on a disjoint training-seed set (after
  `movin2025acdc`), evidence fidelity vs ground truth (Oracle: share of
  evidence users who are true members, share of true members covered), and
  per-feature importance of each counterfactual change (after
  `meulemeester2026cfi`).
- `POST /api/v1/alerts/{id}/what-if`: re-score a ring with modified actionable
  features using the deployed scorer; UI panel with sliders on the alert
  detail page showing the score, threshold and which counterfactual flips the
  decision (after CREDENCE's interactive design, ICDE 2023 demo — add to bib
  only if cited in the paper).
- Semi-global explanation view on the Experiments page: aggregated
  contributions per ring type.
Deliverables: `results/e10_explanations/`, what-if endpoint and panel, paper
table/figure.
Acceptance criteria / tests:
- Unit tests: validity check on a hand-built LR with known closed-form
  counterfactual; stability metric equals 0 for zero perturbation.
- The what-if endpoint returns exactly the scorer's output for the unmodified
  vector.
- Report distributions (median, IQR, counts), not selected examples.
**STOP and wait for my go-ahead.**

# MILESTONE P12: Research A4 + A5 — learned baselines and evasion-strength sweeps
Goal: answer "no GNN baseline" and test camouflage strength.
Tasks:
- Baseline `tabular_ensemble`: gradient boosting (XGBoost or sklearn
  HistGradientBoosting) on the same 19 ring features over all candidate
  groups without the rule stage; train on training seeds, tune on validation
  seeds, test on test seeds — the same protocol as the scorer.
- Baseline `graphsage` (optional extra `[gnn]`, PyTorch Geometric): node
  classifier on the heterogeneous user–attribute graph with a temporal
  train/test split (after `badjie2026ensembles`, `kumar2026tagat`); node
  scores → rings by one grouping rule fixed **before** looking at test results
  and documented (e.g. connected components of top-scored users in the
  hub-weighted projection). Also report node-level AUC for every method,
  labelled as not comparable to YelpChi/Amazon/Elliptic numbers in the
  literature.
- Optional: FastRP/Node2Vec embeddings (GDS) as extra ring features.
- E11 `evasion_strength`: sweep decoy edges per member, low-and-slow rate
  multiplier, identity-rotation period (add config fields if missing, with
  tests); proposed vs cap 10 vs Louvain vs the new baselines (after
  `liu2025robust`, `hu2025hhgfd`).
- Paired Wilcoxon vs proposed on identical streams; effect sizes.
Deliverables: baselines in `src/fraudsim/experiments/baselines.py`,
`results/e11_*`, figures, tables, macros; Experiments page updated.
Acceptance criteria / tests:
- Unit tests: baselines run on a micro-graph; grouping rule deterministic.
- Same stream digests across all methods per (scenario, seed).
- If a baseline beats the proposed method anywhere, it is reported as such in
  README and paper.
**STOP and wait for my go-ahead.**

# MILESTONE P13 (stretch, each item optional and separately approved): A7–A12
Pick in this order, one sub-milestone per item, each with its own STOP:
- P13a A12-hash: HMAC pseudonymisation of device/card/IP ids at ingest
  (`PSEUDONYM_KEY` env); test that detections are identical; explorer shows
  pseudonyms unless the admin reveals (audited).
- P13b A7: simulated analyst (budget b alerts/hour, error rate ε) driving
  `AlertPolicy`; rolling precision/recall with and without feedback, attacker
  feedback on/off (after `giles2023suspicious`).
- P13c A8: prequential metrics on a long drift run; hub-size drift detector
  with hub-weight refit; tests time decay and hysteresis on long streams.
- P13d A9: bipartite peeling / weighted densest-subgraph extractor as an
  ablation arm (after `karaaslanli2025crowd`, `feng2024unified`).
- P13e A10: incremental Louvain baseline (after `zhang2026incremental`).
- P13f A11: extended AMLworld replay (longer slice, 24 h / 7 d windows,
  pattern-type breakdown, rolling behavioural features).
- P13g A12-DP: differentially private aggregate KPIs on a shared dashboard
  (after `dhulipala2022dp`, `li2023dplouvain`).
Acceptance: the same rules as P10–P12 (traceable rows, unit tests with known
answers, paired comparisons, honest reporting of null results).
**STOP after each sub-milestone and wait for my go-ahead.**

# MILESTONE P14: Quality — testing depth, accessibility, full-stack compose
Goal: production-quality engineering.
Tasks:
- Coverage targets: Python ≥ 85% on `src/fraudsim/api/v1/` (report actual),
  Vitest on all hooks and form schemas, MSW for API mocking.
- Playwright e2e suite against the compose stack: login (both roles),
  dashboard live alert, simulator run + replay deep link, triage → case →
  report download, explorer search, rule change with dry run, experiments
  page consistency; screenshots attached to the test report.
- `@axe-core/playwright` on every page (no serious/critical); keyboard-only
  walkthrough test; colour-contrast check of tokens in both themes.
- Performance: Lighthouse (desktop) on dashboard and alert detail, report the
  actual scores; bundle analysis; graph view stays responsive at the node cap.
- `docker-compose.yml`: add `api` (existing `app`, renamed only if needed via
  a new service, keep the old one working), `webapp` (Next.js standalone
  output), `worker` (simulation/detection loop if separated), Neo4j + GDS,
  Redis, optional Postgres profile; healthchecks for all; `make stack-up`
  brings up everything and seeds demo users from `.env`.
- CI: add the e2e job (compose services, in-memory backend allowed for speed,
  Neo4j job nightly), upload Playwright traces on failure.
Deliverables: test reports, compose stack, CI e2e job.
Acceptance criteria / tests: CI green on the branch; `docker compose up` +
`make stack-up` gives a working app at `http://localhost:3000` with the demo
accounts; all reports saved in `docs/reports/p14_*`.
**STOP and wait for my go-ahead.**

# MILESTONE P15: Deployment
Goal: a public demo instance and a documented path to reproduce it.
Tasks (write `docs/deploy.md`, verify every free-tier limit from official docs
and cite the URL):
- Option A (recommended, ASSUMPTION: simplest because the detector is a
  long-running process and the Louvain baseline needs the GDS plugin): one VM
  with docker compose behind Caddy (automatic TLS), volumes for Neo4j, Redis
  and the app DB, nightly backup of the app DB, `restart: unless-stopped`.
- Option B: frontend on Vercel; API + worker as a container on a container
  host; Neo4j AuraDB Free (verify GDS availability and node/relationship
  limits; if GDS is unavailable, disable the Louvain baseline in that
  deployment and say so in the UI); Redis Cloud or Upstash (verify Streams
  command support and connection limits).
- Environment: `.env.example` listing every variable (`DATABASE_URL`,
  `NEO4J_URI/USER/PASSWORD`, `REDIS_URL`, `JWT_SECRET`, `CSRF_SECRET`,
  `PSEUDONYM_KEY`, `DEMO_*`, `NEXT_PUBLIC_API_BASE`, `ALLOWED_ORIGINS`),
  secrets set in the host's secret store, never in git.
- Seeding: `fraudsim seed-demo` loads the course graph, records one
  `demo_story` run, creates demo users; idempotent.
- Health: `/health` (liveness), `/ready` (Neo4j, Redis, DB reachable),
  uptime check, structured logs shipped to stdout; Prometheus `/metrics`
  protected or internal only.
- Demo account: read-mostly analyst account with periodic reset job; admin
  account not public.
- CD: GitHub Actions deploy job on tags only, never on push to main.
Deliverables: `docs/deploy.md`, deploy workflow, live URL in README.
Acceptance criteria / tests: smoke test script against the deployed URL
(health, login as demo analyst, dashboard loads, one simulation runs, report
downloads); results saved to `docs/reports/p15_deploy_smoke.txt`.
**STOP and wait for my go-ahead.**

# MILESTONE P16: Paper update and final documentation
Goal: an updated paper with the Phase 2 results and a complete how-to.
Tasks:
- Paper (`docs/paper/`, existing IEEE conference template; the upload
  `papers_nosql/grfzhhncsfqn.pdf` is the IEEE template instructions — follow
  its formatting rules): new subsections for real-stack latency, ring-level
  calibration and early warning, explanation quality (RQ4), learned baselines
  and evasion strength, and any stretch results; update abstract, Threats to
  Validity (remove only the caveats that new runs actually closed), and
  Conclusion. All numbers via `numbers.tex` macros.
- Bibliography: only papers that are in `papers_nosql/` (or already verified
  in `references.bib`) and published 2020 or later, with DOI/venue/year taken
  from the PDF metadata; no invented references; remove remaining
  `[cite: ...]` placeholders. Exclude the pre-2020 files listed in
  `docs/phase2/ANALYSIS.md`.
- Add a short "System" section or appendix describing the web app as the
  analyst-facing artefact (screenshots from the real app).
- README: final architecture diagram (Mermaid, including webapp, API, worker,
  Neo4j, Redis, app DB), quick start (local, compose, deployed demo), feature
  tour with real screenshots, role matrix, reproduce-paper section, test and
  CI badges, milestone status P1–P16.
- `docs/HOWTO.md` (M9 created this file; extend it, do not replace it): add an
  analyst guide (triage, cases, reports), admin guide (rules, users, audit),
  developer guide (API types, adding a detector, adding a page) and update the
  researcher guide (running experiments, regenerating the paper).
Deliverables: rebuilt `docs/paper/paper.pdf`, updated README, `docs/HOWTO.md`.
Acceptance criteria / tests: `make experiment-all && make paper` regenerates
every new figure and table from scratch; a script checks that every number in
the paper's new sections is a macro; link checker passes on README and docs.
**STOP and wait for my go-ahead.**

# DEFINITION OF DONE
`docker compose up` + `make stack-up` opens a professional web app at
`http://localhost:3000`: an analyst logs in, watches live KPIs and alerts stream
in from Redis Streams, runs and replays fraud-ring scenarios, investigates an
alert with its evidence subgraph, contributions, counterfactuals and what-if
panel, opens a case, labels alerts (which adapts thresholds), explores entities
k hops out, and downloads an evidence-backed PDF report with a SAR-style
summary; an admin versions and dry-runs rule changes. The Experiments page and
the paper show the same numbers, all generated from logged runs. CI is green,
the deployment is live, and README/HOWTO explain everything.

# PROGRESSION
follow the global rules for each milestone
this is a multi-turn conversation
- do not skip milestones
- do not skip any steps within a milestone
- do not jump ahead
- do not skip any output formats (test reports, api docs, PR bodies, screenshots)
- do not summarize
- do not skip any validation or checkpoint steps
- for each milestone, after you implement the deliverables and run all tests,
  pause and wait for my go-ahead
