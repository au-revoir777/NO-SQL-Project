# Web application (Phase 2)

The analyst-facing web app: a Next.js front end in `webapp/` talking to a
versioned FastAPI contract at `/api/v1`. The Phase 2 plan is
[`docs/phase2/phase2_prompt.md`](phase2/phase2_prompt.md); this page documents
what exists now (milestones P1 and P2) and is extended by each milestone.

The M7 dashboard in `web/` (Vite) and every pre-existing API route (`/health`,
`/runs/*`, `/ws`, `/ui`, ...) are unchanged and keep working.

## Architecture

```
webapp/  Next.js 16 App Router, TypeScript strict, Tailwind 4, shadcn/ui
   │     /api/v1/* goes through a route handler (BFF) that forwards cookies to FastAPI
   ▼
FastAPI  src/fraudsim/api/
   ├── v1/              /api/v1 router: request ids, error envelope, sub-routers
   │   ├── errors.py    X-Request-ID middleware, {error: {code, message, request_id}}
   │   ├── auth/        passwords, JWT cookies, CSRF, login rate limit, app audit, deps
   │   ├── schemas/     pydantic v2 models (ErrorEnvelope, Page[T], HealthV1, ...)
   │   └── routers/     system (health), auth, admin, runs, and the planned sub-routers
   ├── main.py          existing routes, /ws, /ui (unchanged)
   └── openapi.py       deterministic OpenAPI serialisation (the committed contract)
src/fraudsim/appdb/      app-state store: SQLAlchemy 2 models + Alembic migrations
```

**App-state store.** Users, cases, case alerts, notes, labels, rule sets,
reports and audit references live in a relational database
(`DATABASE_URL`, default `sqlite:///runs/app.db`; a Postgres URL works the
same way). ASSUMPTION (from the plan, kept): analyst work is not stored in
Neo4j, so TTL pruning of the detection graph can never delete it and tests run
without services. Migrations: `fraudsim db-upgrade` (or `make db-upgrade`).

**Contract.** `docs/api/openapi.json` is generated from the app
(`make openapi`) and committed; the web app's types
(`webapp/src/lib/api/schema.d.ts`) are generated from it with
`openapi-typescript` (`make api-types`) and used through `openapi-fetch`. CI's
`contract` job fails when either file is out of date.

## API conventions (/api/v1)

| Convention | Detail |
|---|---|
| Request id | Every response has `X-Request-ID`; a safe client-supplied id (`[A-Za-z0-9._-]{1,128}`) is echoed, otherwise one is generated. |
| Errors | `{"error": {"code", "message", "request_id", "details?"}}` for 404, 405, 422 (with field-level `details`), 501 and 500 (no internals leaked). Old routes keep `{"detail": ...}`. |
| Pagination | `{"items": [...], "next_cursor": "...", "total": n}` (`Page[T]`), cursor passed back as `?cursor=`. |
| Placeholders | Sub-routers of later milestones answer `501 not_implemented` naming the milestone; no fake data. |

Routes so far:

| Route | Data |
|---|---|
| `GET /api/v1/health` | API version, app DB reachability and Alembic revision, Neo4j (if configured), Redis (pinged if `REDIS_URL` is set) |
| `GET /api/v1/auth/csrf` | sets the CSRF cookie and returns the token |
| `POST /api/v1/auth/login`, `/refresh`, `/logout`; `GET /api/v1/auth/me` | session (see Authentication) |
| `GET /api/v1/runs/current` | the live run from the existing engine (same source as `GET /status`) |
| `POST /api/v1/runs` | start a run (scenario, seed, speed); stops the current one; serialised by a lock |
| `GET /api/v1/runs/current/metrics` | KPI sample of the live run (`?oracle=true` adds labelled ground truth) |
| `GET /api/v1/stream/alerts`, `/stream/metrics` | Server-Sent Events (see Live dashboard) |
| `GET /api/v1/scenarios`, `/scenarios/catalog`, `/scenarios/{name}`; `POST /scenarios/validate`, `/scenarios/yaml`; `PUT /scenarios/custom/{name}` (admin) | scenario builder (see Simulator) |
| `POST /api/v1/runs/current/{pause,resume,stop,speed,rate,inject}`; `GET /runs/current/detectors`, `PATCH /runs/current/detectors/{type}` (admin); `GET /runs/current/graph` | run controls and the live graph |
| `GET /api/v1/replays`, `/replays/{run_id}` | story replays and recorded runs |
| `GET, POST /api/v1/admin/users`; `PATCH /api/v1/admin/users/{id}` | user administration (admin) |
| `/api/v1/{alerts,cases,entities,graph,reports,experiments,rules}` | `501` until their milestone (P5 to P9), behind the role checks below |

## Authentication and roles (P2)

| Piece | Implementation |
|---|---|
| Passwords | argon2id with `argon2-cffi`'s defaults (RFC 9106 low-memory profile: 64 MiB, 3 passes, 4 lanes), minimum 12 characters. Hashing takes about 0.2 s on an idle laptop and several seconds under heavy CPU load, so the handlers that hash run in FastAPI's threadpool, never on the event loop. |
| Session | Two JWTs (HS256, `JWT_SECRET`) in cookies: `fraudsim_access` (15 min, path `/`) and `fraudsim_refresh` (7 days, path `/api/v1/auth`). Both `HttpOnly`, `Secure` (unless `COOKIE_SECURE=0`), `SameSite=Lax`. |
| Revocation | Each token carries the user's `token_version`. Logout, deactivation and a role change increment it, so every earlier token of that user is refused on its next request (the user row is read on each request), not only at expiry. |
| CSRF | Double submit: the readable `fraudsim_csrf` cookie must equal the `X-CSRF-Token` header on every POST/PUT/PATCH/DELETE under `/api/v1`, login included; mismatch is `403 csrf_failed`. |
| Login rate limit | Failures are counted per email and per client IP; 5 failures in 15 minutes (`LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_SECONDS`) answers `429 rate_limited` with `Retry-After`. Redis when `REDIS_URL` is set, in-memory otherwise. |
| Errors | `401 unauthenticated`, `token_expired`, `session_revoked`, `invalid_credentials`; `403 forbidden` (role) and `csrf_failed`. Wrong email and wrong password give the same message. |
| Audit | `LOGIN`, `LOGIN_FAILED`, `LOGIN_RATE_LIMITED`, `LOGOUT`, `USER_CREATED`, `USER_UPDATED` are appended to the hash-chained audit trail in `APP_AUDIT_DIR` (default `runs/app_audit`, run id `app`; check with `fraudsim audit-verify runs/app_audit`) and indexed in the `audit_refs` table. |
| Users | `fraudsim create-user --email ... --role admin` (password prompted, or `--password-env VAR`). Demo accounts only from `DEMO_ADMIN_EMAIL/PASSWORD` and `DEMO_ANALYST_EMAIL/PASSWORD` (`fraudsim seed-users`, also run at API start-up). Accounts are deactivated, never deleted; an admin cannot deactivate or demote themselves. |

Role matrix (enforced on the server by FastAPI dependencies on every router,
and again by the Next.js server layouts; the sidebar only hides what the
server would refuse):

| Area | Anonymous | Analyst | Admin |
|---|---|---|---|
| `GET /api/v1/health`, `/auth/csrf`, `POST /auth/login`, `/auth/refresh` | yes | yes | yes |
| `/auth/me`, `/auth/logout` | 401 | yes | yes |
| `/runs`, `/alerts`, `/cases`, `/entities`, `/graph`, `/reports`, `/experiments`, `/stream` | 401 | yes | yes |
| `/rules`, `/admin/*` | 401 | 403 | yes |
| Pages: Dashboard, Alerts, Cases, Explorer, Reports, Simulator, Replays, Experiments | redirect to `/login` | yes | yes |
| Pages: Rules, Users, Audit | redirect to `/login` | 403 page | yes |
| Original API (`/status`, `/runs/*`, `/scenarios`, `/catalog`, `/graph`, `/rings*`, `/events/recent`, `/oracle`, `/metrics*`, `GET /detectors`, `GET /config`) | 401 | yes | yes |
| Original API: `POST /config`, `POST /detectors/{type}` (live detector settings) | 401 | 403 | yes |
| `/ws` live stream | closed (4401) | yes | yes |
| `GET /health` (original) | yes | yes | yes |

The original routes in `api/main.py` use the same dependencies (POSTs also need
the CSRF header) since the M0 audit (R1). The `/ws` handshake reads the session
cookie: a foreign `Origin` is refused (HTTP 403), a missing or invalid session
is closed with code 4401, and an open socket closes with 4401 when its access
token expires, so the client refreshes and reconnects. CORS allows only
`CORS_ORIGINS` (default `http://localhost:3000,http://localhost:5173`), with
credentials. The M7 dashboard at `/ui` shows a sign-in form and greys out the
admin-only controls for analysts.

**Web side.** `webapp/src/proxy.ts` redirects requests without an access
cookie to `/login?next=...` (only same-site relative paths are accepted as
`next`). The `(app)` layout asks FastAPI `/auth/me` on the server and redirects
when the session is invalid; the `(admin)` layout calls Next's `forbidden()`,
which renders `app/forbidden.tsx` with HTTP status 403
(`experimental.authInterrupts`). The browser only talks to the Next.js origin:
`app/api/v1/[...path]/route.ts` forwards the request, cookies and CSRF header
to `API_BASE_URL` and passes `Set-Cookie` back. The client adds the CSRF header
to unsafe requests and, on a 401, refreshes once and retries.

ASSUMPTION: logout revokes all of the user's sessions (on every device), because
revocation is per user (`token_version`), not per token. This keeps the store to
one integer column; per-device sessions can be added later if needed.

ASSUMPTION: the API trusts the socket address for the rate limit's IP key; behind
a reverse proxy (P14) the forwarded-for header has to be configured in uvicorn.

## Live dashboard (P3)

```
LiveRun broadcast ──► /ws (M7 dashboard, unchanged)
                 └──► StreamPublisher ──► fraudsim:alerts   (each alert and early warning)
                                      ├─► fraudsim:metrics  (KPI sample, ≤ 2/s + one trailing sample)
                                      └─► fraudsim:events   (newest events of each batch)
streams: Redis Streams (XADD MAXLEN~, XREAD BLOCK) if REDIS_URL is set, else in-process
         ──► GET /api/v1/stream/{alerts,metrics} (SSE) ──► Next.js BFF ──► EventSource
```

- **Resume.** Every SSE event carries the stream entry id. A reconnecting
  EventSource sends `Last-Event-ID` and gets exactly the entries after it: no gap
  and no duplicate (tested on the in-process store, and against real Redis in
  the integration job). `?since=` sets the start for a first connection
  (`$` = new only, `0-0` = backlog); `?run_id=` keeps one run. A `: keep-alive`
  comment goes out after 15 s of silence. The response ends when the access token
  expires, and the client refreshes and reconnects from its last id.
- **KPIs** (`stream/publisher.py: kpis()`, the same function behind
  `GET /runs/current/metrics`):
  - events per wall-clock second since the start, pauses excluded;
  - graph size;
  - open alerts and alerts in the run;
  - alerts per **simulated** hour, labelled as not an operational rate;
  - rings by status;
  - detect latency p50/p95/p99 per batch, with the same definition as
    `evaluate_run` (`detect_ms`).

  Simulator ground truth (ring precision, recall, F1, missed rings) appears only
  under `oracle`, labelled "Oracle (simulator ground truth)", and the page shows
  it only behind the toggle.
- **Page.** `components/live/*`:
  - KPI cards with sparklines and explicit loading, empty and error states;
  - latency and throughput charts. Throughput is plotted between samples, so the
    start-up burst does not dominate;
  - the alert feed: risk badge, ring type, size, top reason and age in simulated
    seconds, with a detail dialog;
  - one status per stream.

  Updates are buffered and rendered at most 4 times a second. New alerts with risk
  ≥ 0.8 are announced through an `aria-live` region. Every number belongs to the
  run id in the header: when a new run starts, the page resets.

ASSUMPTION: the alert detail is a dialog with the streamed fields; triage and
the full explanation belong to the Alerts page (P5).

## Simulator and replays (P4)

**Scenario builder.** `ScenarioV1` (`api/v1/schemas/scenario.py`) mirrors the
YAML dialect of `configs/scenarios/*.yaml` key for key:
- unknown keys are rejected, so a typo is an error;
- integers stay integers, so a preset round-trips to the same JSON and the
  same `config_hash`.

The page loads a preset into a form covering every `SimulationConfig` section:
population, benign mix, named hubs, random hubs, drift, rings, random rings
and the adaptive attacker.
- A zod mirror of the constraints gives instant field messages.
- The server validates twice: pydantic gives field-level 422s, which the page
  shows on the matching fields; then `parse_simulation_config` checks the
  cross-field rules.
- "Save as YAML" downloads a file the CLI loads with the same hash.
- Admins can save to `configs/scenarios/custom/` (audited as `SCENARIO_SAVED`;
  `SCENARIOS_CUSTOM_DIR` overrides the folder).

An unedited preset is started by name, so its run is identical to
`fraudsim … --scenario <name>`. An edited one is sent inline and recorded in
full in the run's manifest. Tests check that demo_story seed 7 started from
the UI gives the same stream digest as `fraudsim demo-story --seed 7`, in both
pytest and Playwright.

**Controls and graph.**
- Controls: pause, resume, stop, speed, rate and ring injection for analysts;
  detector toggles for admins (the server returns 403 to an analyst).
  `run_control.start_live_run` serialises run management with a lock.
- Graph: the windowed, capped snapshot of the live store in Cytoscape. Users
  are coloured by detection status. Devices, cards and IPs are shown by kind
  and shape, and hubs are sized by degree. The Oracle overlay (true positive,
  false positive, missed) is labelled as simulator ground truth and is off by
  default. The graph exports to PNG and SVG.

**Replays.** `GET /api/v1/replays/{run_id}` serves the JSON `fraudsim
demo-story` writes, unchanged, from `results/demo_story/` (committed: run
`00434da7845b`, the run behind the README screenshots) or `demo/`.
`/replays/[runId]` ports `story.html`; `lib/replay/story.ts` holds the same
state-at-time rule, seeded layout and deep links. The page has:
- play and pause, speed, a scrubber, a detector switch, and the answer key
  (off by default);
- running scores, and flags at their batch;
- end-of-run cards and the provenance footer;
- deep links `?t=&det=&key=` (the old `#t=` form works too).

`demo/story.html` is unchanged. Playwright checks that `?t=90&det=cap10&key=1`
shows the counts story.html computes from the same JSON.

**Accessibility.** axe (`@axe-core/playwright`) runs on the simulator, replays
and replay pages and reports no serious or critical violations. It found, and
P4 fixed:
- light-mode `--ok`, `--warn` and `--risk-alert` text below 4.5:1;
- the avatar initials;
- the rich-colour toasts;
- a form that re-validated on blur and moved the button under the pointer.

## Alerts and case management (P5)

**Recording.** `AlertRecorder` (`api/v1/cases/recorder.py`) runs inside the
stream publisher. A ring becomes an `alerts` row the first time it raises an
alert or early warning (unique on run and ring id). Later updates refresh its
members, risk, explanation and a capped `history`. Triage fields (status,
assignee) are never overwritten by the engine. A database error is logged and
the live run goes on. Risk and members in the queue are the ring's latest
values, not the values at the moment it was raised; the ring history keeps
each change.

**Workflow.** The API enforces the state machines (`cases/workflow.py`):
- alerts: new → triaged / escalated / closed, triaged ↔ escalated, any → closed;
- cases: open ↔ in_review, → escalated, → closed;
- closing a case needs a resolution (422 without one);
- a closed alert or case can only be reopened by an admin;
- any other move is a 409 `invalid_transition` that lists the allowed targets.

Every change (status, assignment, label, note, case, attachment) is written
to the hash-chained app audit trail (`runs/app_audit`), which `fraudsim
audit-verify` and `GET /api/v1/audit/verify` check.

**Labels and threshold feedback.** `POST /alerts/{id}/labels` stores
confirmed fraud, dismissed (benign) or needs info. If the alert's run is the
API's current run, confirm and dismiss also call that run's
`AlertPolicy.feedback`. The response, and the alert page, show the
threshold before and after. pytest checks that the change equals the same
feedback applied to a copy of the policy.

**Notes** are Markdown text, stored as written and shown as plain text.
Editing one stores a new version that supersedes the old one. Earlier
versions stay readable and are never deleted. Only the author or an admin can
edit a note.

**Cases** group alerts. Attaching an alert freezes its evidence (canonical
JSON, SHA-256). The case page shows the hash and opens the frozen copy, so a
case keeps the evidence it was opened on even if the ring changes later.

**Pages.**
- `/alerts`: the queue. Filters cover status, ring type, detector, risk
  range, time range, assignee and text, with validation (risk in [0, 1], from
  ≤ to). Views can be saved per user. Bulk actions assign, set a status (only
  the targets some selected alert allows), create a case or add to a case.
  Keyboard: `j`/`k` move, `Enter` opens, `x` selects; shift-click selects a
  range.
- `/alerts/[id]`: overview with the score, threshold and calibration bucket,
  and a caveat from E10 (the shipped calibration does not transfer to
  ring-level alerts: ECE 0.10, and rings scored 0.8–0.9 were true rings 29%
  of the time). Evidence as a Cytoscape graph with a table alternative;
  feature contributions; counterfactuals; the ring timeline; labels, notes
  and the audit activity. Create a case or add to one.
- `/cases` and `/cases/[id]`: status transitions (resolution on close),
  priority, assignee, attached alerts with their evidence hash, notes and
  history.
- `/audit` (admin): the trail, filterable by action, actor and object, with
  the hash-chain check.

**Times.** SQLite returns naive datetimes, so the API sends app-database
times without an offset; the web app reads them as UTC (`parseTime`).

**Tests.**
- pytest (`tests/test_cases.py`, 22 tests): state machines, recording from a
  real baseline run, filters, saved views, policy feedback, and a scripted
  triage session verified through the API and the CLI.
- Vitest: filter and selection rules, form schemas, the alert queue (filter
  validation and requests, shift-click range, bulk status, `j`/`k`/`Enter`),
  and the activity list.
- Playwright (`e2e/cases.spec.ts`): an analyst opens the top alert, reads the
  evidence table, adds a note, labels it (threshold change shown), creates a
  case and escalates it. The form refuses to close it without a resolution.
  An admin then finds the case entries in the audit view and the chain
  verifies. axe reports no serious or critical violations on the queue, alert,
  case, cases list and audit pages.

## Entity and graph explorer (P6)

**One walk, two backends.** `fraudsim.graph.explore.Explorer` implements
search, entity details and the k-hop neighbourhood once, on top of a few read
primitives (`MemoryReads` for the in-memory store, `Neo4jReads` in Cypher).
The neighbourhood is the detector's dirty-region expansion
(`GraphStore.expand`) made visible:
- one hop is a shared device, card or IP, or a transfer in either direction;
- the first hop crosses attributes with at most `max_fanout` active users,
  later hops at most `far_fanout` (defaults: the run's `EngineConfig`, 250 and
  20);
- an attribute over the cap is shown but not crossed. Its `stop` says why,
  for example `hub: 12 active users > cap 10 at hop 1`. Attributes beyond k
  are marked `depth limit`;
- edges carry the hub weight the hub-aware detector uses
  (`inverse_log_degree`);
- relationship-type and time-window filters (simulated time), and a node
  limit (`max_nodes`, at most 1000, with `truncated` set when reached).
  Nothing unbounded is sent to the browser.

With no filter, the users returned equal `GraphStore.expand` for the same
seeds and caps. pytest checks this for every user of the course graph, k = 1–3
and four cap settings. In CI, the integration job checks that Neo4j and the
in-memory store give identical search, entity and neighbourhood answers on
the course graph, filters included.

**Sources** (`?source=`):
- `run`: the current run's store;
- `course`: the course seed graph, which `seed.py` builds and the existing
  event-generator bridge replays into memory (built once per process);
- `neo4j`: the configured database, for example the graph `seed.py` loads.
  The Cypher tolerates that graph's missing `active` and `t` properties.

**Endpoints.**
- `GET /api/v1/entities/search?q=&kind=&source=`: id-prefix search.
  Neo4j uses `STARTS WITH` on the uniqueness-constraint indexes.
- `GET /api/v1/entities/{kind}/{id}`: attributes or users, degree, hub
  weight, transfers, a timeline, and (current run) linked alerts and tracked
  rings.
- `GET /api/v1/graph/neighbourhood?seed=kind:id&k=&rel=&since_t=&until_t=&max_fanout=&far_fanout=&max_nodes=`
- `GET /api/v1/graph/rings/{ring_id}`: a tracked ring of the current run. It
  gives the member set after every tracker change (rebuilt backwards from the
  current members and the `added`/`removed` of each change), the size history,
  and the attributes two or more members share.

In-memory handlers are async: they run on the event loop between engine
batches, so they never read the store while the engine writes it. Neo4j reads
go to the threadpool.

**Pages.**
- `/explorer`: search with type filters. Ctrl+K (Cmd+K) opens the same search
  from any page.
- `/explorer/[kind]/[id]`: the entity page and its neighbourhood graph
  (Cytoscape). Controls cover k, relationship types, the UTC time window, both
  caps and the node limit. Click a node (or Expand in the node table) to add
  its one-hop neighbourhood. "Pin to compare" keeps an entity, and another
  entity's page can then overlay both and count the users reached from each
  and from both. Exports: PNG, SVG and JSON.
- `/explorer/rings/[ringId]`: membership over time, size chart, shared
  attributes and the neighbourhood. Alert pages of the current run link their
  members and ring here.

**Tests.** pytest `tests/test_explorer.py` (micro-graphs with exact nodes,
edges and stop reasons; filters; node cap; entity details; the expand
equivalence; the API) and `tests/test_integration_explorer.py` (Neo4j). Vitest
covers merging, comparison and the UTC window. Playwright
`e2e/explorer.spec.ts`:
- searching `device_007` on the course graph lists the four Ring A users,
  read from the README table;
- the walk from u13 stops at `ip_001` with a first-hop cap of 10;
- expand, pin and compare, and Ctrl+K;
- an alert opens its ring over time;
- the graph canvas is drawn;
- axe reports no serious or critical violations.

## Investigation reports (P7)

`POST /api/v1/reports` builds a report for a scope: runs, cases and/or
alerts, optionally limited to rings first seen in a simulated-time window.

**Sections** (each optional):
- executive summary;
- alert table;
- per-ring detail with the evidence subgraph;
- contributions chart;
- counterfactuals;
- timeline;
- analyst notes and labels;
- SAR-style summary: subjects, shared attributes, transfers and amounts, the
  activity window, typology, evidence references, and an analyst narrative
  from the notes;
- run metrics;
- limitations, including the E10 calibration caveat.

The "Oracle (simulator ground truth)" comparison per run is added only on
request. Every page carries the fixed disclaimer "Generated from simulated
data for research/demo purposes. Not a regulatory filing." in its footer,
together with the page number.

**Where the numbers come from.**
- Run facts (`fraudsim.reports.run_logs`) are read only from the run's log
  directory: `manifest.json`, `events.jsonl`, `detections.jsonl`,
  `rings.jsonl`, and `ground_truth.jsonl` for the Oracle section. Live runs
  gained `sync_logs()`, which flushes their streams and writes the ring states
  and the ledger, so a report reads the current run as it stands.
- A ring attached to a case uses its frozen evidence and cites the snapshot's
  SHA-256. Other rings use the app-DB alert, or the run log's first
  alert/early-warning record when the run was not recorded in the app DB.

**Rendering.** Jinja2 (`reports/templates/report.html.j2`) with print CSS
(A4, page numbers in `@page` margin boxes). Charts are static SVG from
matplotlib in the paper's style, with no date metadata, a fixed hash salt and
a seeded graph layout, so the HTML is byte-stable apart from `generated_at`.

ASSUMPTION: the evidence subgraph is drawn server-side (networkx +
matplotlib), not captured from Cytoscape. It is deterministic and needs no
JavaScript at build time.

ASSUMPTION: PDF is printed with `--print-to-pdf` by the headless Chromium
that the web app's Playwright installs (`FRAUDSIM_CHROMIUM` overrides). This
avoids WeasyPrint's native libraries on Windows and adds no Python
dependency. Without Chromium, PDF requests answer 503 `pdf_unavailable`;
HTML still works. New pinned dependency: `jinja2==3.1.6`.

**Records.** Each report gets:
- an id;
- the run ids and scenario config hashes it used;
- the SHA-256 of its file (`$FRAUDSIM_RUNS_DIR/app_reports/<id>.<html|pdf>`),
  with `<id>.json` (its numbers, without charts) beside it;
- a `REPORT_GENERATED` audit entry with the hash.

Endpoints: `GET /api/v1/reports` lists them, `GET /api/v1/reports/{id}` gives
one, and `GET /api/v1/reports/{id}/download` returns the file (`text/html` or
`application/pdf`).

**Pages.** `/reports` has the builder (runs, cases, alert ids, time window,
sections, Oracle, format) and the list with re-download. Case pages link to it
with the case in scope (`/reports?case=<id>`).

**Tests.**
- pytest `tests/test_reports.py`:
  - every run number equals a recount of the JSONL files done in the test;
  - every raised ring appears once;
  - the Oracle section appears only on request, with its label;
  - the record lists the runs used, and the file hash is in the audit entry;
  - the frozen snapshot hash and the case narrative are in the report;
  - golden: two independent runs of baseline seed 7 render the same bytes
    apart from the timestamp, and match `tests/golden/report_baseline_seed7.html`
    (charts left out of the committed copy, because SVG path data can change
    with the matplotlib version);
  - PDF: content type, magic bytes and hash.
- Vitest: the builder's schema.
- Playwright `e2e/reports.spec.ts`: from a case page, generate a PDF,
  download it (`%PDF-`, over 10 KB, `application/pdf`), see it listed with one
  ring, and run axe.

## What-if and counterfactuals (P11)

`POST /api/v1/alerts/{id}/what-if` re-scores an alert's ring with changed
**actionable** features, using the deployed scorer: the run's own scorer when
the run is current, else the shipped model (path and SHA-256 in the response).
Nothing is stored. Alerts keep the scored feature vector with their
explanation, so older alerts recorded before P11 answer 409 `no_features`.
With no changes, the score is exactly the scorer's output for the scored
vector (tested). The alert page's **What-if** tab has sliders for the
actionable features, the score against the threshold, and an Apply button for
each counterfactual.

Counterfactuals now aim just below the raw score at which the interpolated
isotonic calibration reaches the threshold. Before P11 they aimed at the
calibrator's breakpoint and, in E12, none of them flipped the decision. See
`docs/research/e12_results.md` and the protocol's amendment 1.

## Running it

```bash
pip install -e ".[dev,redis]"
make db-upgrade                       # python -m fraudsim.cli db-upgrade
python -m fraudsim.cli api --port 8000
cd webapp && npm ci && npm run dev    # http://localhost:3000
```

To sign in, create an account first (`python -m fraudsim.cli create-user
--email you@example.test --role admin`) or set the `DEMO_*` variables from
`.env.example` before starting the API. Set `JWT_SECRET` (any long random
string); without it a random one is generated per process and sessions end on
restart. Over plain `http://` on a host other than `localhost`, set
`COOKIE_SECURE=0` for local use only.

`API_BASE_URL` (server-side, default `http://127.0.0.1:8000`) tells Next.js
where FastAPI is. For a production build: `npm run build && npm run start`.

| Make target | What it runs |
|---|---|
| `make db-upgrade` | `fraudsim db-upgrade` |
| `make openapi` | `fraudsim export-openapi --out docs/api/openapi.json` |
| `make api-types` | `make openapi`, then `openapi-typescript` in `webapp/` |
| `make webapp-dev` / `webapp-build` / `webapp-test` | `next dev` / `npm ci && next build` / eslint + tsc + Vitest |
| `make e2e` | Playwright: starts the API on :8100 (fresh `runs/e2e` DB, fixture users) and `next build && next start` on :3100; first run `npm run e2e:install` once |
| `make stack-up` | `docker compose --profile app up -d --build` (the `webapp` service is added in P14) |

## Pinned versions

Exact versions (no `^`/`~`), each the newest release at least two weeks old on
2026-10-22. Python additions are pinned in `pyproject.toml`; older Python
dependencies keep their existing minimum versions.

**Exception: security fixes.** A patch release that fixes a published advisory
may be pinned before it is two weeks old, with the owner's approval. On
2026-10-24, `npm audit` reported two critical (remote code execution) and one
high advisory against next 16.4.0 ([GHSA-2464-fhr4-w9xw](https://github.com/advisories/GHSA-2464-fhr4-w9xw),
[GHSA-673q-mjm6-r5xr](https://github.com/advisories/GHSA-673q-mjm6-r5xr),
[GHSA-p3m5-59mp-jv5r](https://github.com/advisories/GHSA-p3m5-59mp-jv5r); fixed in 16.4.1, released
2026-10-14), and one high advisory against zod 4.6.5
([GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5); fixed in 4.6.6, released 2026-10-11).
Both were upgraded with approval; `npm audit --omit=dev` now reports 0
vulnerabilities.

| Package | Version | Note |
|---|---|---|
| next, eslint-config-next | 16.4.1 | security exception (see above) |
| react, react-dom, @types/react, @types/react-dom | 19.3.0 | |
| typescript | 5.9.3 | 7.0 lacks the JS API typescript-eslint needs; 6.0 is outside openapi-typescript 7.13's peer range (`^5`) |
| tailwindcss, @tailwindcss/postcss | 4.3.3 | |
| radix-ui | 1.7.0 | shadcn/ui primitives (new-york style, via `shadcn@4.21.4 add`) |
| next-themes | 0.4.6 | |
| @tanstack/react-query | 5.104.1 | |
| openapi-typescript / openapi-fetch | 7.13.0 / 0.17.0 | |
| geist | 1.7.2 | Geist Sans / Geist Mono via `next/font` |
| lucide-react | 1.52.0 | |
| class-variance-authority, clsx, tailwind-merge, tw-animate-css | 0.7.1, 2.1.1, 3.7.0, 1.4.0 | |
| vitest, vite, @vitejs/plugin-react | 5.0.3, 8.3.3, 6.1.2 | |
| jsdom | 26.1.0 | 30.x requires Node ≥ 22.22 |
| @testing-library/react, /dom, /jest-dom, /user-event | 16.3.3, 10.4.2, 7.0.1, 14.6.7 | |
| eslint | 9.39.5 | 10.x not yet supported by all of eslint-config-next's plugins |
| prettier, prettier-plugin-tailwindcss | 3.9.9, 0.8.1 | |
| fastapi | 0.115.0 | Python; exact because the committed OpenAPI contract depends on its schema output |
| pydantic | 2.9.2 | Python; exact for the same reason (pydantic-core 2.23.4 follows) |
| sqlalchemy | 2.0.35 | Python |
| alembic | 1.20.0 | Python |
| mypy | 1.18.2 | Python (dev) |
| pyjwt | 2.15.1 | Python |
| argon2-cffi | 25.1.0 | Python |
| react-hook-form, @hookform/resolvers | 7.89.0, 5.9.1 | |
| zod | 4.6.6 | security exception (see above) |
| sonner | 2.0.8 | toasts (shadcn `sonner`) |
| @playwright/test | 1.64.0 | Chromium is installed with `npm run e2e:install` |
| @axe-core/playwright | 4.13.0 | 4.14.0 was under two weeks old |
| cytoscape, cytoscape-svg | 3.34.3, 0.4.0 | 3.34.4 was under two weeks old; cytoscape ships its types |

`webapp/.npmrc` sets `legacy-peer-deps=true`: npm 10.9's resolver crashes
(`Cannot read properties of null (reading 'edgesOut')`) on vitest 5's optional
peer set. Every peer the app needs is listed explicitly instead.

## Quality gates

| Check | Command | CI job |
|---|---|---|
| Python lint | `ruff check` / `ruff format --check` | `py-lint` |
| Python types | `mypy` strict on `api/v1`, `appdb`, `api/openapi.py` | `py-lint` |
| Python tests | `pytest -m "not integration"` | `py-test` |
| Web lint and types | `npm run lint`, `npm run typecheck`, `npm run format:check` | `web-lint` |
| Web unit tests | `npm run test` (Vitest, jsdom) | `web-test` |
| Web build | `npm run build` | `web-build` |
| End to end | `npx playwright test` | `e2e` |
| Contract | regenerate OpenAPI and TS types, diff | `contract` |

mypy on the whole pre-Phase-2 code base currently reports 67 errors in 24 files
(`mypy src/fraudsim`); the strict gate covers the Phase 2 packages only, and the
older code is not regressed.

## Design system

Implemented from the plan's design system: shadcn/ui (new-york) on Tailwind 4,
colour tokens as CSS variables in `webapp/src/app/globals.css` (shadcn neutrals
plus the domain tokens `--risk-*`, `--benign`, `--node-*`, `--ok`, `--warn`),
light/dark/system theme via `next-themes`, Geist fonts, tabular numerals
(`.tabular`), reduced-motion support, and an ESLint rule that rejects hex
colours in components, and one that rejects imports of the `cn` npm
package (the shadcn CLI adds it; the app uses `cn` from `@/lib/utils`). Status is never shown by colour alone (icon + text).
The sidebar groups (Monitor, Investigate, Simulate, Research, Admin) are in
`webapp/src/lib/nav.ts`; pages of later milestones show an empty state naming
their milestone.
