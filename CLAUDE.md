# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`AGENTS.md` is the maintained source of truth for this repo's stack, commands, and layout. Read it first, and keep it updated when tools, commands, or CI change. This file summarizes it and adds a few points that matter for Claude Code.

## Commands

This is a polyglot monorepo with two independent dependency systems: Django at the repo root and a pnpm workspace in `packages/*`. Syncing one side does not install the other.

Node (pnpm 12, Node 24+; CI uses Node 26):

```sh
pnpm install
pnpm lint && pnpm typecheck && pnpm test      # verify order; each delegates via pnpm -r
pnpm --filter api-client test                 # one package (address packages by name, not path)
pnpm --filter api-client exec node --test src/index.test.ts   # one test file
pnpm --filter web dev                         # Vite on :5173; needs Django running
pnpm --filter web build
```

Django (Python 3.14 in CI; the venv lives at `.venv`):

```sh
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # Windows: .venv\Scripts\...
.venv/bin/python manage.py runserver          # :8000
.venv/bin/python manage.py check
.venv/bin/python -m pytest                    # all tests (pytest-django; pytest.ini sets config.settings)
.venv/bin/python -m pytest api/test_products.py::test_create_product_requires_auth -q   # one test
.venv/bin/python manage.py makemigrations     # commit migration files
```

`AGENTS.md` and `opencode.jsonc` give Windows paths (`.venv\Scripts\python.exe`). On Linux or macOS, use `.venv/bin/python`.

CI (`.github/workflows/ci.yml`) runs `pnpm lint/typecheck/test` plus `pnpm --filter web build` in one job, and `manage.py check` plus `pytest` in another.

## Architecture

- **Django API** (`config/` project, `api/` app, `manage.py` at the root):
  - DRF `ProductViewSet` at `/api/products/`.
  - `GET /api/health/` returns `{"status": "ok"}`. `POST /api/auth/login/` (username + password) returns `{token, username}`.
  - Auth: token auth with `IsAuthenticatedOrReadOnly`, so reads are public and writes need `Authorization: Token <key>`.
  - Lists use `SearchFilter` (`?search=`) and `api.pagination.StandardPagination`, which returns `{count, next, previous, results}`.
  - `price` is a `DecimalField` serialized as a **string**, and the TypeScript types mirror that.
- **OpenAPI contract:** `drf-spectacular` serves `/api/schema/` and `/api/docs/`. A snapshot is committed as `openapi.json` at the repo root. When you change server-side schemas, regenerate it in this order:
  1. `.venv/bin/python manage.py spectacular --file openapi.json --format openapi-json` (Windows: `.venv\Scripts\python.exe`)
  2. `pnpm --filter api-client-generated generate`
- **`packages/api-client`:** a **hand-written** TypeScript client (`createApiClient(baseUrl, {token?})`, throws `ApiError`). Its tests stub global `fetch` and use `node --test`. This is the client `web` actually consumes.
- **`packages/api-client-generated`:** `@hey-api/openapi-ts` output in `src/`. Generation **wipes `src/`**, so the hand-written entry `index.ts` sits at the package root. It has no tests, and nothing in the workspace imports it yet. Keep it in sync with `openapi.json`, but update `api-client` by hand when the API changes.
- **`packages/web`:** Vite + React 19. `vite.config.ts` proxies `/api` to Django on `127.0.0.1:8000`, so the client uses an empty base URL and no CORS setup is needed. The login token lives only in React state.

## Gotchas

- Keep TypeScript on 5.x in every package, and don't move to TS 6.1+ or 7: `typescript-eslint` 8 requires TypeScript below 6.1. Ranges differ per package (`api-client` uses `^5.5.0`, while `web` and `api-client-generated` use `^5.9.3`), so leave them as they are.
- ESLint 10 uses flat configs (`eslint.config.mjs` in each package). Generated `src/**/*.gen.ts` files are excluded from linting.
- For local dev, create a demo user with `createsuperuser`; none is shipped.
