# AGENTS.md

> **Baseline scaffold.** The repo has a working monorepo skeleton — a pnpm workspace under
> `packages/*`, a Django project rooted at the top level, and **no CI and no real application
> code yet**. Commands below were verified against this state (2026-10-10).

## Stack
- **Polyglot monorepo:** Django (Python) API/server + Node packages in one repo.
- **Django:** 6.1.2, settings module `config.settings`, `manage.py` at the **repo root**. Default
  DB is sqlite (`db.sqlite3`, gitignored). Python deps: `.venv` + `requirements.txt`.
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

Django — run via the venv: `.venv\Scripts\python.exe manage.py <cmd>` on Windows, or activate
`.venv` first (if PowerShell blocks activation, `Set-ExecutionPolicy -Scope Process Bypass`):
- `python -m venv .venv` · `pip install -r requirements.txt`
- `manage.py runserver` · `check` · `test`
- `manage.py makemigrations` / `migrate` — **commit migration files**

Expected verify order when changing code: **lint -> typecheck -> test** (Node), plus
`manage.py check` / `manage.py test` (Django).

## Layout
- Repo root: `manage.py`, `config/` (Django project incl. `settings.py`), `package.json`,
  `pnpm-workspace.yaml`, `requirements.txt`, `opencode.jsonc`, `AGENTS.md`.
- `packages/api-client` — placeholder package; its lint/typecheck/test scripts are stubs that
  echo and exit 0 (keeps `pnpm -r <script>` from failing until real tooling lands).
- Gitignored: `.venv/`, `node_modules/`, `db.sqlite3`, `__pycache__/`.

## OpenCode setup
- `opencode.jsonc` defines `/verify` (Node verify loop) and `/verify-server` (Django checks +
  tests) commands. `AGENTS.md` is auto-loaded as instructions.

## Keep current
No CI and no real lint/typecheck/test tooling (eslint/tsc/pytest) exists yet — the package scripts
are stubs. When real tooling and a CI gate land, record the exact commands and gate order here
from those sources of truth.