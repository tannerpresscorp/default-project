# AGENTS.md

> **Working skeleton.** pnpm workspace (`packages/*`) + Django project rooted at the top level.
> Minimal real code (health endpoint, placeholder API client), real tooling, and a CI gate.
> Commands below were verified on 2026-10-10.

## Stack
- **Polyglot monorepo:** Django (Python) API/server + Node packages in one repo.
- **Django:** 6.1.2, settings module `config.settings`, `manage.py` at the **repo root**. Default
  DB is sqlite (`db.sqlite3`, gitignored). Python deps: `.venv` + `requirements.txt`
  (+ `requirements-dev.txt` for pytest). App `api` exposes `GET /api/health/`.
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
- Per package: `pnpm --filter api-client <script>`
- `api-client` toolchain: TypeScript (`tsc --noEmit`), ESLint 10 flat config
  (`eslint.config.mjs`), tests via Node's built-in runner (`node --test src`, no test framework dep).

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
  `views.py`, `urls.py`, `test_health.py`), `package.json`, `pnpm-workspace.yaml`,
  `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `opencode.jsonc`, `AGENTS.md`.
- `packages/api-client` — TypeScript package (`src/index.ts` + `src/index.test.ts`) with real
  lint/typecheck/test scripts.
- `.github/workflows/ci.yml` — CI gate: `node` job (`pnpm lint/typecheck/test`) and `django` job
  (`manage.py check`, `pytest`); runs on push/PR at github.com/imatthewtanner/default-project.
- Gitignored: `.venv/`, `node_modules/`, `db.sqlite3`, `__pycache__/`.

## OpenCode setup
- `opencode.jsonc` defines `/verify` (Node verify loop) and `/verify-server` (Django checks +
  tests) commands. `AGENTS.md` is auto-loaded as instructions.

## Keep current
Tooling and CI are minimal but real (ESLint 10 + tsc + node:test for Node; pytest-django for
Django; GitHub Actions gate). Update this file from sources of truth whenever tools, commands,
or the CI gate change.