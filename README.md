# Default Project

[![CI](https://github.com/tannerpresscorp/default-project/actions/workflows/ci.yml/badge.svg)](https://github.com/tannerpresscorp/default-project/actions/workflows/ci.yml)

A polyglot monorepo built around two co-located systems:

- **Product catalog** — a Django + Django REST Framework API, a React + Vite web UI, and typed TypeScript clients.
- **Agent platform foundation** — an additive FastAPI control plane, Temporal workflow worker, PostgreSQL/pgvector persistence, and shared Python packages for identity, policy, model/tool gateways, retrieval, usage budgets, observability and evaluations.

The two systems share one repository and one CI gate, but they have independent dependencies, databases and virtual environments. The Django app keeps its SQLite database and `.venv`; the platform uses PostgreSQL, Alembic and `.venv-platform`.

> The agent platform is a **foundation, not a production-ready service**. No vendor model calls, remote tool execution, MCP transport or real sandbox backend are implemented. See [Security](#security) and [docs/architecture/overview.md](docs/architecture/overview.md) before relying on it.

## Contents

- [Highlights](#highlights)
- [Requirements](#requirements)
- [Quick start: product catalog](#quick-start-product-catalog)
- [Product catalog API](#product-catalog-api)
- [Quick start: agent platform](#quick-start-agent-platform)
- [Platform components](#platform-components)
- [Common commands](#common-commands)
- [Regenerating the OpenAPI client](#regenerating-the-openapi-client)
- [Configuration](#configuration)
- [Repository layout](#repository-layout)
- [Testing and CI](#testing-and-ci)
- [Security](#security)
- [Documentation](#documentation)

## Highlights

### Product catalog

- CRUD for `Product` at `/api/products/` (DRF `ModelViewSet`, JSON).
- Token authentication: reads are public, writes require `Authorization: Token <key>`.
- Search across `name`, `sku` and `description` with `?search=`.
- Page-number pagination through `?page=` and `?page_size=` (default 10, max 100).
- OpenAPI schema at `/api/schema/` and Swagger UI at `/api/docs/`.
- React UI with login, product search, pagination, create and delete.
- Hand-written TypeScript client (`api-client`) plus a generated client (`api-client-generated`) driven by the committed `openapi.json`.

### Agent platform

- Authenticated runtime API: submit, read, list and cancel agent runs; poll status over SSE; read/replace monthly budgets; ingest and search retrieval documents.
- Deterministic Temporal workflows for agent runs and human approvals, with database and model effects in activities.
- Tenant-scoped pgvector retrieval with forced PostgreSQL row-level security.
- Static model routing and tool policy with allowlists, JSON Schema validation, idempotency, durable approvals and timeouts — all offline.
- Append-only usage ledger with optional monthly admission budgets.
- Deny-by-default sandbox boundary (no code execution), deterministic evaluation runner, Sentry/OpenTelemetry integration and bounded Prometheus counters.

## Requirements

| Tool | Version / notes |
| --- | --- |
| Python | 3.12+ for the platform (pinned in CI); the Django CI job uses 3.14 |
| Node.js | 24+ (CI uses 26) |
| pnpm | 12.8.1 (`packageManager` in `package.json`) |
| Docker | Optional; used by the local platform Compose stack |
| Temporal CLI | Optional; required only for platform workflow integration tests |

The Django and platform environments are separate. Do not install both dependency sets into one virtual environment.

## Quick start: product catalog

### 1. Start the Django API

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Bash:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

The API is available at <http://127.0.0.1:8000>. The demo credentials `alice` / `secret123` are **not** shipped — create your own user with `createsuperuser` or a Django shell.

### 2. Start the web UI

In a second terminal:

```bash
pnpm install
pnpm --filter web dev
```

Open <http://localhost:5173>. Vite proxies `/api/*` to Django on port 8000, so no CORS configuration is needed and the browser only talks to the Vite origin.

The login token is kept in React state only; reloading the page signs you out.

## Product catalog API

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/api/health/` | Public | Health check |
| `POST` | `/api/auth/login/` | Public | Exchange `username` + `password` for a token |
| `GET` | `/api/products/` | Public | List products (`search`, `page`, `page_size`) |
| `POST` | `/api/products/` | Token | Create a product |
| `GET` | `/api/products/{id}/` | Public | Retrieve a product |
| `PATCH` / `PUT` | `/api/products/{id}/` | Token | Update a product |
| `DELETE` | `/api/products/{id}/` | Token | Delete a product |
| `GET` | `/api/schema/` | Public | OpenAPI 3 schema (JSON) |
| `GET` | `/api/docs/` | Public | Swagger UI |

`Product` fields are `id`, `name`, `description`, `price`, `sku`, `created_at` and `updated_at`. `price` is a `DecimalField` and is serialized as a **string** in JSON.

Example requests:

```bash
# Obtain a token
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"your-user","password":"your-password"}'

# Create a product (replace <token> with the value returned above)
curl -X POST http://127.0.0.1:8000/api/products/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Widget","sku":"W-1","price":"19.99","description":"A useful widget"}'

# Search and paginate
curl "http://127.0.0.1:8000/api/products/?search=widget&page=1&page_size=10"
```

List responses use the shape `{count, next, previous, results}`.

## Quick start: agent platform

Full setup, environment requirements and PowerShell equivalents live in [docs/architecture/development.md](docs/architecture/development.md). The short version:

```bash
python3.12 -m venv .venv-platform
.venv-platform/bin/python -m pip install -r requirements-platform-dev.txt

docker compose -f infra/local/compose.yaml up -d --wait postgres redis

export PLATFORM_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform'
export PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@127.0.0.1:55432/platform'
.venv-platform/bin/python -m alembic upgrade head

.venv-platform/bin/python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

On Windows use `.\.venv-platform\Scripts\python.exe` and see the PowerShell section of the development guide. The local database passwords are public and intended only for the loopback-bound Compose stack; never reuse them outside local development.

The API exposes:

- `GET /health/live` and `GET /health/ready`
- `GET /openapi.json`
- `GET /metrics` (Prometheus text counters)
- `GET /v1/session` (authenticated identity)
- `POST/GET /v1/runs`, `GET /v1/runs/{id}/events` (SSE), `POST /v1/runs/{id}/cancel`
- `GET/PUT /v1/budget`
- `POST /v1/retrieval/documents` and `POST /v1/retrieval/search`

Protected `/v1` routes require a trusted OIDC bearer token. Configure `PLATFORM_OIDC_ISSUER`, `PLATFORM_OIDC_AUDIENCE` and `PLATFORM_OIDC_JWKS_URL`; without them, authentication and readiness fail closed. No tenant header is trusted — tenant context comes from the verified token claim.

Run submission also requires Temporal. Without `PLATFORM_TEMPORAL_ADDRESS`, run endpoints return `503`. To start a local worker:

```bash
temporal server start-dev --namespace default

export PLATFORM_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform'
export PLATFORM_TEMPORAL_ADDRESS='127.0.0.1:7233'
.venv-platform/bin/python -m apps.workflow_worker.worker
```

## Platform components

| Path | Responsibility |
| --- | --- |
| [`apps/api`](apps/api) | FastAPI control plane: health, metrics, identity and runtime endpoints |
| [`apps/model_gateway`](apps/model_gateway/README.md) | Static logical model routing, bounded requests, timeouts and a deterministic offline provider |
| [`apps/tool_gateway`](apps/tool_gateway/README.md) | Tenant allowlists, JSON Schema validation, audited idempotent invocations, durable approvals |
| [`apps/workflow_worker`](apps/workflow_worker/README.md) | Deterministic Temporal workflows (`AgentRunWorkflow`, `ToolApprovalWorkflow`) and worker |
| [`apps/retrieval`](apps/retrieval/README.md) | Tenant-scoped pgvector chunk storage and cosine HNSW search |
| [`apps/sandbox_manager`](apps/sandbox_manager/README.md) | Deny-by-default sandbox boundary; no real execution backend |
| [`apps/eval_service`](apps/eval_service/README.md) | Deterministic offline evaluation runner and fixed smoke dataset |
| [`packages/auth`](packages/auth) | OIDC/JWT verification and authenticated principal context |
| [`packages/persistence`](packages/persistence) | SQLAlchemy models, repositories, Alembic migrations and RLS-aware database helpers |
| [`packages/usage`](packages/usage/README.md) | Append-only usage ledger and monthly admission budgets |
| [`packages/model_clients`](packages/model_clients/README.md) | Model and embedding provider contracts plus a deterministic offline embedder |
| [`packages/observability`](packages/observability) | Structured logging, bounded metrics and Sentry scrubbing |
| [`packages/policies`](packages/policies/README.md) | Shared authorization policy contracts |
| [`packages/schemas`](packages/schemas) | Bounded request/response and domain contracts |
| [`packages/domain`](packages/domain) | Core domain types such as run status |
| [`packages/config`](packages/config) | Environment-backed platform settings |
| [`packages/mcp`](packages/mcp/README.md) | Intentional non-goal boundary; no MCP client, server or transport |

PostgreSQL is authoritative for platform records. Redis is provisioned in the local Compose stack for future ephemeral use but is not connected to the platform. See the [architecture overview](docs/architecture/overview.md), [ADRs](docs/adr/) and [operations runbook](docs/runbooks/platform-operations.md). The Helm chart under [`infra/helm/agent-platform`](infra/helm/agent-platform) is gated, linted and rendered in CI, but never applied.

## Common commands

### Node / pnpm

| Task | Command |
| --- | --- |
| Install workspace dependencies | `pnpm install` |
| Lint every package | `pnpm lint` |
| Type-check every package | `pnpm typecheck` |
| Test every package | `pnpm test` |
| Build the web UI | `pnpm --filter web build` |
| Run the web dev server | `pnpm --filter web dev` |
| Regenerate the API client | `pnpm --filter api-client-generated generate` |

Package scripts can be run individually with `pnpm --filter <name> <script>`; pnpm addresses packages by name, not directory path.

### Django

| Task | Command |
| --- | --- |
| Checks | `.venv\Scripts\python.exe manage.py check` |
| Tests | `.venv\Scripts\python.exe -m pytest` |
| Migrations | `.venv\Scripts\python.exe manage.py makemigrations` / `migrate` |
| Dev server | `.venv\Scripts\python.exe manage.py runserver` |

Use `.venv/bin/python` on Unix.

### Agent platform

| Task | Command |
| --- | --- |
| Lint | `.venv-platform\Scripts\python.exe -m ruff check apps packages tests` |
| Format check | `.venv-platform\Scripts\python.exe -m ruff format --check apps packages tests` |
| Type-check | `.venv-platform\Scripts\python.exe -m mypy` |
| Unit tests | `.venv-platform\Scripts\python.exe -m pytest -c pyproject.toml tests/unit` |
| Integration tests | `.venv-platform\Scripts\python.exe -m pytest -c pyproject.toml tests/integration` |
| Migrate | `.venv-platform\Scripts\python.exe -m alembic upgrade head` |
| Worker | `.venv-platform\Scripts\python.exe -m apps.workflow_worker.worker` |

On Unix, `make lint`, `make typecheck`, `make test`, `make migrate`, `make integration-test` and `make worker` wrap the same commands. Integration tests require a migrated `platform_test` database, `PLATFORM_TEST_DATABASE_URL`, and optionally `TEMPORAL_CLI_PATH` for the Temporal workflow tests.

## Regenerating the OpenAPI client

When the Django API schema changes, regenerate and commit both artifacts:

```powershell
# 1. Refresh the committed schema snapshot
.\.venv\Scripts\python.exe manage.py spectacular --file openapi.json --format openapi-json

# 2. Regenerate the TypeScript client
pnpm --filter api-client-generated generate
```

The generated client lives in `packages/api-client-generated/src/`. Its hand-written entry point is `packages/api-client-generated/index.ts` at the package root, because generation wipes `src/`.

## Configuration

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SENTRY_DSN` | Django | Sentry DSN; inert when unset |
| `PLATFORM_SENTRY_DSN` | FastAPI platform | Sentry DSN; must use HTTPS; inert when unset |
| `VITE_SENTRY_DSN` | Web | Frontend Sentry DSN; inert when unset |
| `SENTRY_ENVIRONMENT`, `PLATFORM_SENTRY_ENVIRONMENT`, `VITE_SENTRY_ENVIRONMENT` | Apps | Sentry environment label |
| `PLATFORM_DATABASE_URL` | Platform API/worker | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `PLATFORM_MIGRATION_DATABASE_URL` | Alembic | Migration role URL; never used for application traffic |
| `PLATFORM_OIDC_ISSUER` | Platform API | Trusted HTTPS OIDC issuer |
| `PLATFORM_OIDC_AUDIENCE` | Platform API | Expected token audience |
| `PLATFORM_OIDC_JWKS_URL` | Platform API | JWKS endpoint for signature verification |
| `PLATFORM_OIDC_TENANT_CLAIM` | Platform API | UUID tenant claim name (default `tenant_id`) |
| `PLATFORM_TEMPORAL_ADDRESS` | Platform API/worker | Temporal frontend address; unset disables run dispatch |
| `PLATFORM_TEMPORAL_NAMESPACE` | Platform API/worker | Temporal namespace (default `default`) |
| `PLATFORM_TEMPORAL_TASK_QUEUE` | Platform API/worker | Task queue (default `agent-runs`) |
| `PLATFORM_OTEL_ENABLED` | Platform API | Enable OpenTelemetry instrumentation |
| `PLATFORM_OTEL_TRACES_ENDPOINT` | Platform API | OTLP HTTP traces endpoint |
| `TEMPORAL_CLI_PATH` | Integration tests | Temporal CLI executable; tests are skipped without it |

Python apps read the process environment; they do not load `.env` files. Templates are in [`.env.example`](.env.example), [`packages/web/.env.example`](packages/web/.env.example) and [`infra/local/platform.env.example`](infra/local/platform.env.example).

## Repository layout

```text
.
├── api/                        Django app: Product CRUD, auth, health, tests
├── config/                     Django project settings and URL configuration
├── apps/
│   ├── api/                    FastAPI control plane and runtime endpoints
│   ├── model_gateway/          Logical model routing (offline provider only)
│   ├── tool_gateway/           Tool registry, policy, approvals and validation
│   ├── workflow_worker/        Temporal workflows and worker
│   ├── retrieval/              Tenant-scoped pgvector retrieval
│   ├── sandbox_manager/        Deny-by-default sandbox boundary
│   └── eval_service/           Deterministic offline evaluation runner
├── packages/
│   ├── api-client/             Hand-written TypeScript API client
│   ├── api-client-generated/   Client generated from openapi.json
│   ├── web/                    React + Vite web UI
│   ├── auth/ config/ domain/ policies/ schemas/
│   ├── persistence/            Models, repositories, migrations and DB helpers
│   ├── usage/                  Usage ledger and monthly budgets
│   ├── observability/          Logging, metrics and Sentry
│   ├── model_clients/          Model and embedding provider contracts
│   └── mcp/                    Non-goal boundary (no MCP transport)
├── docs/                       Architecture, ADRs and runbooks
├── infra/                      Dockerfile, Helm chart and local Compose stack
├── tests/                      Platform unit and integration tests
├── openapi.json                Committed Django API schema snapshot
├── manage.py                   Django entry point
├── pyproject.toml              Ruff, mypy and platform pytest configuration
├── pytest.ini                  Django pytest configuration
└── .github/workflows/ci.yml    CI gate
```

## Testing and CI

Run the relevant checks before opening a pull request:

- **Node:** `pnpm lint` → `pnpm typecheck` → `pnpm test` → `pnpm --filter web build`
- **Django:** `manage.py check` → `pytest`
- **Platform:** Ruff check + format check → `mypy` → unit tests → integration tests

The GitHub Actions gate in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs five jobs:

1. **Node** — pnpm install, lint, typecheck, test, and web build.
2. **Helm** — `helm lint --strict` plus gated and enabled template renders (never applied).
3. **Image** — builds the container image and runs non-root/read-only health smoke tests.
4. **Django** — Python 3.14, `manage.py check` and `pytest`.
5. **Platform** — Python 3.12, Ruff, mypy, unit tests, and PostgreSQL/pgvector plus Temporal integration tests against a dedicated test database.

CI runs on every push and pull request.

## Security

- The platform validates RS256 bearer tokens against a configured HTTPS JWKS endpoint, checking issuer, audience, expiry, subject and a signed UUID tenant claim. It does not issue users, tokens or tenants.
- Every `/v1` route derives tenant context from the verified principal, never from a request field. PostgreSQL row-level security and tenant-scoped composite foreign keys provide a second isolation layer.
- Runtime database credentials must be non-superuser, non-BYPASSRLS and non-owners; migration credentials are separate.
- RLS does **not** contain a compromised process or arbitrary SQL execution. Avoid SQL injection and keep database privileges minimal.
- No real external model or tool execution exists yet. The sandbox boundary denies by default.
- Existing Django settings are development settings and are **not** production-safe.

Please report vulnerabilities privately rather than opening a public issue. See [SECURITY.md](SECURITY.md) and [docs/architecture/security.md](docs/architecture/security.md).

## Documentation

- [Architecture overview](docs/architecture/overview.md)
- [Local development](docs/architecture/development.md)
- [Security model](docs/architecture/security.md)
- [Multi-tenancy and RLS](docs/architecture/multi-tenancy.md)
- [Agent runtime](docs/architecture/agent-runtime.md)
- [Model gateway](docs/architecture/model-gateway.md) · [Tool gateway](docs/architecture/tool-gateway.md)
- [Retrieval](docs/architecture/retrieval.md) · [Usage and budgets](docs/architecture/usage.md)
- [Sandbox boundary](docs/architecture/sandbox.md) · [Evaluations](docs/architecture/evaluations.md)
- [Observability](docs/architecture/observability.md)
- [Architecture decision records](docs/adr/)
- [Operational runbooks](docs/runbooks/)
- [Agent instructions for coding assistants](AGENTS.md)
