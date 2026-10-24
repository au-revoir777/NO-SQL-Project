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
