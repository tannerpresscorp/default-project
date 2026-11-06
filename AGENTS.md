# AGENTS.md

> **Working skeleton.** pnpm workspace (`packages/*`) + Django project rooted at the top level.
> Minimal real code (health endpoint, placeholder API client), real tooling, and a CI gate.
> Commands below were verified on 2026-10-10.

## Stack
- **Polyglot monorepo:** Django (Python) API/server + Node packages in one repo.
- **Django:** 6.1.2 + Django REST Framework 3.18, settings module `config.settings`, `manage.py`
  at the **repo root**. Default DB is sqlite (`db.sqlite3`, gitignored). Python deps: `.venv` +
  `requirements.txt` (+ `requirements-dev.txt` for pytest). App `api` exposes `GET /api/health/`
  and full CRUD on `Product` at `/api/products/` (DRF ModelViewSet, JSON). `price` is a
  `DecimalField`, serialized as a **string** in JSON.
- **Auth:** DRF token auth (`rest_framework.authtoken`, header `Authorization: Token <key>`).
  `POST /api/auth/login/` (username + password) returns `{token, username}` (LoginView, an
  `ObtainAuthToken` subclass). Products use `IsAuthenticatedOrReadOnly`: **reads are public,
  writes require a token** (anonymous writes → 401). Demo user for local dev: `alice` /
  `secret123` (not shipped; create via `manage.py createsuperuser` or a shell).
- **Search + pagination:** products use DRF `SearchFilter` (`?search=` across name/sku/description)
  and page-number pagination via `api.pagination.StandardPagination` (`page` + `page_size` params,
  default `page_size` 10, max 100). List shape: `{count, next, previous, results}`.
- **OpenAPI:** `drf-spectacular` 0.30 (`/api/schema/` JSON, `/api/docs/` Swagger UI; both public).
  A committed schema snapshot lives at the repo root as **`openapi.json`** (JSON format) — the
  source for the generated client. `LoginView` declares its request/response schemas explicitly
  via `@extend_schema` (`LoginRequestSerializer` / `LoginResponseSerializer`).
- **Node:** pnpm workspace (`pnpm-workspace.yaml` → `packages/*`). Root scripts delegate with
  `pnpm -r`. Commit `pnpm-lock.yaml`; `node_modules/` is gitignored.
- **Error monitoring:** Sentry is optional in all three apps and inert without a DSN —
  `PLATFORM_SENTRY_DSN` (FastAPI), `SENTRY_DSN` (Django), `VITE_SENTRY_DSN` (web). Each app
  disables PII, request bodies, cookies and query strings and redacts credential headers before
  export. Env templates: `.env.example` and `packages/web/.env.example`.

## Two independent dependency systems
- pnpm does **not** install Python deps and vice versa — sync both sides on dependency changes.
- Python env is a **plain venv + pip** at `.venv`; a fresh checkout has no usable Python env until
  the venv exists, is activated, and `pip install -r requirements.txt` has run.
- pnpm addresses packages by **name via `pnpm --filter <pkg>`, not by directory path.**

## Agent platform foundation (separate from Django)
- `apps/api` is an additive FastAPI control-plane foundation; it does not replace the product API.
  Python 3.12 dependencies are in `requirements-platform.txt` and `requirements-platform-dev.txt`;
  use a separate `.venv-platform` so the existing Django environment remains intact.
- `packages/{auth,config,domain,observability,persistence,schemas}` are shared Python platform
  packages. PostgreSQL and Alembic own platform persistence, not Django migrations. Tenant claims
  must be verified and DB work must use transaction-local RLS context with a non-owner,
  non-superuser, non-BYPASSRLS runtime role. See `docs/architecture/multi-tenancy.md`.
- Local setup and explicit commands (including isolated integration-test database migration) are
  in `docs/architecture/development.md`. The original Django pytest config targets `api/`; run
  platform tests with `pytest -c pyproject.toml tests/unit` and `tests/integration` separately.
- Platform checks: `python -m ruff check apps packages tests`, `python -m ruff format --check
  apps packages tests`, `python -m mypy`, and the platform pytest commands. Do not call placeholder
  gateways, runtime, workflows, retrieval or sandbox implemented; they are later phases.
- CI also has a Python 3.12 platform job that runs these checks and PostgreSQL isolation tests
  against a dedicated test database. Later-phase container, evaluation and deployment gates are
  not implemented yet.

## Commands (verified)
Node / workspace — root scripts delegate across all packages:
- `pnpm install` · `pnpm lint` (= `pnpm -r lint`) · `pnpm typecheck` · `pnpm test`
- Per package: `pnpm --filter api-client <script>` / `pnpm --filter api-client-generated <script>` /
  `pnpm --filter web <script>`
- `api-client` toolchain: TypeScript (`tsc --noEmit`), ESLint 10 flat config
  (`eslint.config.mjs`), tests via Node's built-in runner (`node --test src`, no test framework dep).
  Client surface: `createApiClient(baseUrl, {token?})` → `health` / `login` / `setToken` /
  `listProducts({search?, page?, page_size?})` → `PaginatedProducts` / `getProduct` /
  `createProduct` / `updateProduct` (PATCH) / `deleteProduct`, throwing `ApiError` on non-2xx.
  `Product.price` is typed as a string (mirrors DRF serialization). Unit tests stub global fetch.
- `api-client-generated` toolchain: `@hey-api/openapi-ts` v0.99 emits a typed fetch client into
  `src/` (client/core modules + `sdk.gen.ts` / `types.gen.ts` / `index.ts`) from the committed
  `openapi.json`. The hand-written **`index.ts` at the package root** (package entry) wraps it
  with `createApiClient({baseUrl, token?})` — it lives **outside `src/`** because `pnpm --filter
  api-client-generated generate` wipes `src/` on every run. Generated files (`src/**/*.gen.ts`)
  are skipped by ESLint. No test script (skipped by `pnpm -r test`). Regeneration pipeline:
  1. `.venv\Scripts\python.exe manage.py spectacular --file openapi.json --format openapi-json`
  2. `pnpm --filter api-client-generated generate`
- `web` toolchain: Vite 8 (rolldown) + React 19 + strict TS, ESLint 10 flat config with
  `eslint-plugin-react-hooks` (`configs.flat['recommended-latest']`). No unit tests yet — the
  `test` script is absent, so `pnpm -r test` skips it. `typescript` is pinned to `^5.9` because
  `typescript-eslint` 8 requires `<6.1` (do **not** bump to TS 7/native).
- Frontend dev flow: run Django first (`manage.py runserver` on 8000), then `pnpm --filter web dev`
  (Vite on 5173). The browser only talks to the Vite origin — `vite.config.ts` proxies `/api/*` to
  Django, so no CORS setup is needed and the client is used with an empty base URL. The store has
  a login form (token kept in React state only — lost on reload), product search, pagination
  controls, and create/delete (both require login server-side).

Django — run via the venv: `.venv\Scripts\python.exe manage.py <cmd>` on Windows, or activate
`.venv` first (if PowerShell blocks activation, `Set-ExecutionPolicy -Scope Process Bypass`):
- `python -m venv .venv` · `pip install -r requirements.txt` (dev: `-r requirements-dev.txt`)
- `manage.py runserver` · `check`
- `pytest` — primary Django test runner (config: `pytest.ini`, plugin pytest-django)
- `manage.py makemigrations` / `migrate` — **commit migration files** (authtoken's tables come
  from DRF's own migrations when you `migrate` after adding `rest_framework.authtoken`)

Expected verify order when changing code: **lint -> typecheck -> test** (Node), plus
`manage.py check` / `manage.py test` (Django). When touching the schema server-side, regenerate
`openapi.json` and the generated client (see above) so committed types stay fresh.

## Layout
- Repo root: `manage.py`, `config/` (Django project incl. `settings.py` with `REST_FRAMEWORK` +
  `SPECTACULAR_SETTINGS`), `api/` (Django app: `views.py`, `serializers.py`, `urls.py`,
  `pagination.py`, `models.py`, `migrations/`, `test_health.py`, `test_products.py`,
  `test_auth.py`), `openapi.json` (committed schema snapshot), `package.json`,
  `pnpm-workspace.yaml`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`,
  `opencode.jsonc`, `AGENTS.md`.
- `packages/api-client` — hand-written TypeScript package (`src/index.ts` + `src/index.test.ts`)
  with lint/typecheck/test scripts.
- `packages/api-client-generated` — `@hey-api/openapi-ts` output in `src/` + hand-written root
  `index.ts` entry; `openapi-ts.config.ts` reads `../../openapi.json`.
- `packages/web` — React frontend consuming `api-client` (`index.html`, `src/main.tsx`,
  `src/App.tsx`, `src/style.css`, `vite.config.ts` with the Django proxy). `dist/` is gitignored.
- `.github/workflows/ci.yml` — CI gate: `node` job (`pnpm lint/typecheck/test` +
  `pnpm --filter web build`), `django` job (`manage.py check`, `pytest`) and `platform` job
  (Ruff, mypy, unit and PostgreSQL integration tests); runs on push/PR at
  github.com/imatthewtanner/default-project.
- Gitignored: `.venv/`, `node_modules/`, `db.sqlite3`, `__pycache__/`, `web/dist/` + build output.

## OpenCode setup
- `opencode.jsonc` defines `/verify` (Node verify loop) and `/verify-server` (Django checks +
  tests) commands. `AGENTS.md` is auto-loaded as instructions.
- This repo is **private**. For issues/PRs the `gh` CLI is the reliable path (`GH_TOKEN`, a
  classic PAT with `repo` scope). The GitHub MCP server (`MCP_DOCKER` > `github-official`) takes
  its token from the Docker MCP secret `github.personal_access_token` (`docker mcp secret ls`),
  but an authorized OAuth grant (`docker mcp oauth`) takes precedence over that secret. The
  gateway caches credentials at startup, so after changing secrets run `opencode service
  restart`; otherwise GitHub MCP calls fail with `failed to connect: calling "initialize": EOF`.

## Keep current
Tooling and CI are minimal but real (ESLint 10 + tsc + node:test for Node; pytest-django for
Django; GitHub Actions gate). Update this file from sources of truth whenever tools, commands,
or the CI gate change.
