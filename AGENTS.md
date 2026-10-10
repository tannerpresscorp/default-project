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
- **Node:** pnpm workspace (`pnpm-workspace.yaml` → `packages/*`). Root scripts delegate with
  `pnpm -r`. Commit `pnpm-lock.yaml`; `node_modules/` is gitignored.

## Two independent dependency systems
- pnpm does **not** install Python deps and vice versa — sync both sides on dependency changes.
- Python env is a **plain venv + pip** at `.venv`; a fresh checkout has no usable Python env until
  the venv exists, is activated, and `pip install -r requirements.txt` has run.
- pnpm addresses packages by **name via `pnpm --filter <pkg>`, not by directory path.**

## Commands (verified)
Node / workspace — root scripts delegate across all packages:
- `pnpm install` · `pnpm lint` (= `pnpm -r lint`) · `pnpm typecheck` · `pnpm test`
- Per package: `pnpm --filter api-client <script>` / `pnpm --filter web <script>`
- `api-client` toolchain: TypeScript (`tsc --noEmit`), ESLint 10 flat config
  (`eslint.config.mjs`), tests via Node's built-in runner (`node --test src`, no test framework dep).
  Client surface: `createApiClient(baseUrl)` → `health` / `listProducts` / `getProduct` /
  `createProduct` / `updateProduct` (PATCH) / `deleteProduct`, throwing `ApiError` on non-2xx.
  `Product.price` is typed as a string (mirrors DRF serialization). Unit tests stub global fetch.
- `web` toolchain: Vite 8 (rolldown) + React 19 + strict TS, ESLint 10 flat config with
  `eslint-plugin-react-hooks` (`configs.flat['recommended-latest']`). No unit tests yet — the
  `test` script is absent, so `pnpm -r test` skips it. `typescript` is pinned to `^5.9` because
  `typescript-eslint` 8 requires `<6.1` (do **not** bump to TS 7/native).
- Frontend dev flow: run Django first (`manage.py runserver` on 8000), then `pnpm --filter web dev`
  (Vite on 5173). The browser only talks to the Vite origin — `vite.config.ts` proxies `/api/*` to
  Django, so no CORS setup is needed and the client is used with an empty base URL.

Django — run via the venv: `.venv\Scripts\python.exe manage.py <cmd>` on Windows, or activate
`.venv` first (if PowerShell blocks activation, `Set-ExecutionPolicy -Scope Process Bypass`):
- `python -m venv .venv` · `pip install -r requirements.txt` (dev: `-r requirements-dev.txt`)
- `manage.py runserver` · `check`
- `pytest` — primary Django test runner (config: `pytest.ini`, plugin pytest-django)
- `manage.py makemigrations` / `migrate` — **commit migration files**

Expected verify order when changing code: **lint -> typecheck -> test** (Node), plus
`manage.py check` / `manage.py test` (Django).

## Layout
- Repo root: `manage.py`, `config/` (Django project incl. `settings.py`), `api/` (Django app:
  `views.py`, `serializers.py`, `urls.py`, `models.py`, `migrations/`, `test_health.py`,
  `test_products.py`), `package.json`, `pnpm-workspace.yaml`, `requirements.txt`,
  `requirements-dev.txt`, `pytest.ini`, `opencode.jsonc`, `AGENTS.md`.
- `packages/api-client` — TypeScript package (`src/index.ts` + `src/index.test.ts`) with real
  lint/typecheck/test scripts.
- `packages/web` — small React frontend consuming `api-client` (`index.html`, `src/main.tsx`,
  `src/App.tsx`, `src/style.css`, `vite.config.ts` with the Django proxy). `dist/` is gitignored.
- `.github/workflows/ci.yml` — CI gate: `node` job (`pnpm lint/typecheck/test` +
  `pnpm --filter web build`) and `django` job (`manage.py check`, `pytest`); runs on push/PR at
  github.com/imatthewtanner/default-project.
- Gitignored: `.venv/`, `node_modules/`, `db.sqlite3`, `__pycache__/`.

## OpenCode setup
- `opencode.jsonc` defines `/verify` (Node verify loop) and `/verify-server` (Django checks +
  tests) commands. `AGENTS.md` is auto-loaded as instructions.

## Keep current
Tooling and CI are minimal but real (ESLint 10 + tsc + node:test for Node; pytest-django for
Django; GitHub Actions gate). Update this file from sources of truth whenever tools, commands,
or the CI gate change.