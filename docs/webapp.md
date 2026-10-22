# Web application (Phase 2)

The analyst-facing web app: a Next.js front end in `webapp/` talking to a
versioned FastAPI contract at `/api/v1`. The Phase 2 plan is
[`docs/phase2/phase2_prompt.md`](phase2/phase2_prompt.md); this page documents
what exists now (milestone P1) and is extended by each milestone.

The M7 dashboard in `web/` (Vite) and every pre-existing API route (`/health`,
`/runs/*`, `/ws`, `/ui`, ...) are unchanged and keep working.

## Architecture

```
webapp/  Next.js 16 App Router, TypeScript strict, Tailwind 4, shadcn/ui
   │     /api/v1/* is forwarded to FastAPI (P1: rewrite; P2: cookie-forwarding BFF)
   ▼
FastAPI  src/fraudsim/api/
   ├── v1/              /api/v1 router: request ids, error envelope, sub-routers
   │   ├── errors.py    X-Request-ID middleware, {error: {code, message, request_id}}
   │   ├── schemas/     pydantic v2 models (ErrorEnvelope, Page[T], HealthV1, ...)
   │   └── routers/     system (health), runs, and the planned sub-routers
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

Routes in P1:

| Route | Data |
|---|---|
| `GET /api/v1/health` | API version, app DB reachability and Alembic revision, Neo4j (if configured), Redis (pinged if `REDIS_URL` is set) |
| `GET /api/v1/runs/current` | the live run from the existing engine (same source as `GET /status`) |
| `GET /api/v1/{auth,alerts,cases,entities,graph,reports,experiments,rules,stream,admin}` | `501` until their milestone (P2 to P9) |

## Running it

```bash
pip install -e ".[dev,redis]"
make db-upgrade                       # python -m fraudsim.cli db-upgrade
python -m fraudsim.cli api --port 8000
cd webapp && npm ci && npm run dev    # http://localhost:3000
```

`API_BASE_URL` (server-side, default `http://127.0.0.1:8000`) tells Next.js
where FastAPI is. For a production build: `npm run build && npm run start`.

| Make target | What it runs |
|---|---|
| `make db-upgrade` | `fraudsim db-upgrade` |
| `make openapi` | `fraudsim export-openapi --out docs/api/openapi.json` |
| `make api-types` | `make openapi`, then `openapi-typescript` in `webapp/` |
| `make webapp-dev` / `webapp-build` / `webapp-test` | `next dev` / `npm ci && next build` / eslint + tsc + Vitest |
| `make e2e` | placeholder until the Playwright suite starts in P2 |
| `make stack-up` | `docker compose --profile app up -d --build` (the `webapp` service is added in P14) |

## Pinned versions

Exact versions (no `^`/`~`), each the newest release at least two weeks old on
2026-10-22. Python additions are pinned in `pyproject.toml`; older Python
dependencies keep their existing minimum versions.

| Package | Version | Note |
|---|---|---|
| next, eslint-config-next | 16.4.0 | |
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
| sqlalchemy | 2.0.35 | Python |
| alembic | 1.20.0 | Python |
| mypy | 1.18.2 | Python (dev) |

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
colours in components. Status is never shown by colour alone (icon + text).
The sidebar groups (Monitor, Investigate, Simulate, Research, Admin) are in
`webapp/src/lib/nav.ts`; pages of later milestones show an empty state naming
their milestone.
