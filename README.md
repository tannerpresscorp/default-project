# Default Project

A polyglot monorepo containing a Django product-catalog API and React client, alongside an
independent Python agent-platform foundation. The platform is additive: it has its own FastAPI
control plane, PostgreSQL persistence, migrations, and Python environment; it does not replace the
Django API.

## What's here

- **Django API** (`api/`, `config/`): product CRUD, token login, search, pagination, and OpenAPI
  documentation. SQLite is the local default.
- **React web app** (`packages/web/`): product search and pagination, login, and authenticated
  product creation/deletion. Vite proxies `/api/*` to Django.
- **TypeScript API clients** (`packages/api-client/` and `packages/api-client-generated/`): a
  hand-written client used by the web app, plus a generated client based on `openapi.json`.
- **Agent platform** (`apps/`, shared Python packages in `packages/`): a FastAPI runtime, model and
  tool gateway foundations, tenant-scoped retrieval, usage budgets, deterministic Temporal
  workflows, and evaluation tooling.

The platform is intentionally foundational rather than a production agent service: model and tool
execution use deterministic in-process implementations, the sandbox denies execution, and there
are no vendor model adapters or network/MCP tools. See the [architecture overview](docs/architecture/overview.md)
for component boundaries and current limitations.

## Prerequisites

- Python for Django and Python 3.12 for the platform.
- Node.js 24+ and pnpm 12.8.1 for the workspace (CI uses Node 26).
- For the platform, PostgreSQL with pgvector. Docker Compose can provide the local database; a
  native PostgreSQL setup is also documented. The Temporal CLI is needed to run a local
  Temporal server or the workflow integration tests.

Python and pnpm dependencies are independent; install each only for the parts you intend to run.

## Run the Django API and web app

From the repository root, create the Django environment, install development dependencies, migrate
the local SQLite database, and start the API:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`. In another terminal,
install the Node workspace dependencies and run the web app:

```sh
pnpm install
pnpm --filter web dev
```

Open <http://127.0.0.1:5173>. To create products, first create a Django user with
`.venv/bin/python manage.py createsuperuser`, then sign in through the web app.
The checked-in Django settings are for development and are not production-ready.

The API is available at `http://127.0.0.1:8000`:

| Endpoint | Description |
| --- | --- |
| `GET /api/health/` | Health check |
| `POST /api/auth/login/` | Exchange a username and password for a token |
| `/api/products/` | Product list and CRUD |
| `/api/schema/` | OpenAPI schema |
| `/api/docs/` | Swagger UI |

Product reads are public; writes require `Authorization: Token <key>`. Product lists accept
`?search=`, `?page=`, and `?page_size=` (default 10, maximum 100). The API returns page-number
pagination, and product `price` values are serialized as strings.

## Run the platform foundation

The platform uses its own `.venv-platform`, PostgreSQL/pgvector database, and local configuration;
it does not use Django's database or migrations. Follow the detailed
[platform development guide](docs/architecture/development.md)
for setup, database roles, OIDC configuration, local services, the API, and optional Temporal
worker. The guide also documents the native-PostgreSQL and PowerShell paths.

In brief, local development uses Python 3.12, `requirements-platform-dev.txt`, and the Compose
services in `infra/local/compose.yaml`. The API listens on `127.0.0.1:8001`; its health, readiness,
and OpenAPI endpoints are `/health/live`, `/health/ready`, and `/openapi.json`. Protected routes
require a trusted OIDC issuer and fail closed without valid identity configuration. The runtime
run endpoints also require Temporal to be configured; otherwise they return 503.

## Checks and tests

Run the Node workspace checks and frontend build:

```sh
pnpm lint
pnpm typecheck
pnpm test
pnpm --filter web build
```

Run Django checks and tests:

```sh
.venv/bin/python manage.py check
.venv/bin/python -m pytest
```

Run platform checks and unit tests with the platform environment:

```sh
.venv-platform/bin/python -m ruff check apps packages tests
.venv-platform/bin/python -m ruff format --check apps packages tests
.venv-platform/bin/python -m mypy
.venv-platform/bin/python -m pytest -c pyproject.toml tests/unit
```

Platform integration tests require a separately migrated `platform_test` PostgreSQL database with
the expected non-superuser runtime role. Temporal workflow tests additionally require the Temporal
CLI and are skipped if it is unavailable. Follow the [development guide](docs/architecture/development.md)
for safe test database setup and exact environment variables. CI runs the Node checks and web
build, Django checks and tests, and platform checks plus PostgreSQL/Temporal integration tests.

## Documentation

- [Platform architecture](docs/architecture/overview.md)
- [Local development and test setup](docs/architecture/development.md)
- [Security model and limitations](docs/architecture/security.md)
- [Multi-tenancy and database isolation](docs/architecture/multi-tenancy.md)
- [Operational runbooks](docs/runbooks/README.md)
- [Security policy](SECURITY.md)

The committed root `openapi.json` is the Django API schema snapshot. When changing Django API
schemas, regenerate the snapshot and the generated client; see [AGENTS.md](AGENTS.md) for the
commands and workspace conventions.
