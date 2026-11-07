# Local development

Requires Python 3.12 and PostgreSQL with the `pgvector` extension. The Compose stack uses `pgvector/pgvector:pg16`; a native PostgreSQL installation needs pgvector built and installed separately. Temporal integration tests also require the Temporal CLI; the tests start an isolated local dev server from that binary. The original Django environment and pnpm workflow remain unchanged. On Windows use the equivalent `.venv-platform\Scripts\python.exe` instead of `.venv-platform/bin/python`; `make` is optional.

```sh
python3.12 -m venv .venv-platform
.venv-platform/bin/python -m pip install -r requirements-platform-dev.txt
docker compose -f infra/local/compose.yaml up -d --wait postgres redis
export PLATFORM_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform'
export PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@127.0.0.1:55432/platform'
.venv-platform/bin/python -m alembic upgrade head
.venv-platform/bin/python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

Local database passwords are intentionally public and **only** for this loopback-bound development stack. The migration role owns the schema but is not a superuser; the Compose service starts as the superuser `platform_migrator`, while a native installation must provision the extension once as a database administrator. Never use migration credentials for application traffic. Configure `PLATFORM_OIDC_ISSUER`, `PLATFORM_OIDC_AUDIENCE`, and `PLATFORM_OIDC_JWKS_URL` to use a trusted HTTPS OIDC issuer. The issuer must guarantee the configured UUID tenant claim represents authorized membership for the token subject. Without OIDC configuration, protected endpoints fail closed and readiness reports 503. `PLATFORM_OIDC_TENANT_CLAIM` defaults to `tenant_id`. The app does not issue users, tokens, or tenants.

Health: `GET http://127.0.0.1:8001/health/live`; readiness: `/health/ready`; OpenAPI: `/openapi.json`; Prometheus text counters: `/metrics`; authenticated identity: `GET /v1/session` with a bearer token. No tenant header is trusted. The authenticated runtime surface is `POST/GET /v1/runs`, `GET /v1/runs/{id}/events` (SSE), `POST /v1/runs/{id}/cancel`, `GET/PUT /v1/budget`, `POST /v1/retrieval/documents` and `POST /v1/retrieval/search`. Runs are created in `PENDING` and dispatched to Temporal only when `PLATFORM_TEMPORAL_ADDRESS` is set; otherwise those endpoints fail closed with 503. Budgets are optional and checked at submission.

Error monitoring is optional: export `PLATFORM_SENTRY_DSN` (FastAPI), `SENTRY_DSN` (Django) and set `VITE_SENTRY_DSN` in `packages/web/.env.local` (React). Without them the SDKs stay inert. The Python apps read the process environment; they do not load `.env` files.

```sh
.venv-platform/bin/python -m ruff check apps packages tests
.venv-platform/bin/python -m ruff format --check apps packages tests
.venv-platform/bin/python -m mypy
.venv-platform/bin/python -m pytest -c pyproject.toml tests/unit
# Dedicated test database; never point this at a shared or production database.
export PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@127.0.0.1:55432/platform_test'
.venv-platform/bin/python -m alembic upgrade head
export PLATFORM_TEST_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform_test'
# Optional: Temporal workflow tests are skipped without this binary.
export TEMPORAL_CLI_PATH="$HOME/.temporalio/bin/temporal"
.venv-platform/bin/python -m pytest -c pyproject.toml tests/integration
```

The integration tests require the dedicated database name `platform_test` and a non-superuser, non-BYPASSRLS application role. Without its URL pytest reports a skip, not a passing integration verification. Temporal tests start an isolated in-memory dev server, so they do not need a running Temporal service; without `TEMPORAL_CLI_PATH` they are skipped. Download the CLI from the [Temporal release page](https://github.com/temporalio/cli/releases) or install it with `brew install temporal`. The tests create unique rows and do not clean them up. Run migrations using the migration URL for the target database before testing. `make dev`, `test`, `lint`, `typecheck`, `migrate`, and `integration-test` are equivalent on Unix, with the same environment requirements. Compose data is persistent and is not removed by these commands.

To run the Temporal worker against a local dev server:

```sh
temporal server start-dev --namespace default
export PLATFORM_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform'
export PLATFORM_TEMPORAL_ADDRESS='127.0.0.1:7233'
.venv-platform/bin/python -m apps.workflow_worker.worker
```

Set the same `PLATFORM_TEMPORAL_ADDRESS`, `PLATFORM_TEMPORAL_NAMESPACE` and `PLATFORM_TEMPORAL_TASK_QUEUE` on the API process to enable `POST /v1/runs`. Migration `0006_budgets_usage_idempotency` adds `tenant_budgets` and usage idempotency; run `alembic upgrade head` for both databases after pulling it. The integration suite covers the runtime API, budgets, SSE and retrieval against PostgreSQL, plus real Temporal completion, failure and cancellation.

### Native PostgreSQL instead of Docker

A local PostgreSQL service can replace the Compose database; it uses the default port `5432` rather than `55432`. Create the same development roles and databases, then run the grants from `infra/local/postgres-init.sql` against both databases:

```sql
CREATE ROLE platform_migrator LOGIN PASSWORD 'local_migrator_only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE platform_app LOGIN PASSWORD 'local_app_only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE platform OWNER platform_migrator;
CREATE DATABASE platform_test OWNER platform_migrator;
```

Point `PLATFORM_DATABASE_URL`, `PLATFORM_MIGRATION_DATABASE_URL` and `PLATFORM_TEST_DATABASE_URL` at `127.0.0.1:5432` and run `alembic upgrade head` for both databases. Keep the migration role out of application traffic and keep `platform_app` non-owner and non-BYPASSRLS.

Native installations must provide `pgvector`. Build it with the PostgreSQL development headers or install a distribution package, then create the extension once per database as a superuser:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The application and migration roles intentionally lack permission to create the extension; migration `0003_retrieval` only succeeds after it exists. Compose and CI already satisfy this because their PostgreSQL image includes pgvector and the bootstrap role is a superuser.

## PowerShell

Use `py -0p` to select a Python 3.12 installation. For example, with the Astral CPython 3.12.16 installation shown by the launcher:

```powershell
py -V:Astral/CPython3.12.16 -m venv .venv-platform
.\.venv-platform\Scripts\python.exe -m pip install -r requirements-platform-dev.txt
docker compose -f infra/local/compose.yaml up -d --wait postgres redis
$env:PLATFORM_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform'
$env:PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@127.0.0.1:55432/platform'
.\.venv-platform\Scripts\python.exe -m alembic upgrade head
.\.venv-platform\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

For integration tests, point the migration URL at `/platform_test`, migrate that database, and set `PLATFORM_TEST_DATABASE_URL` to the application-role URL ending in `/platform_test`. Set `TEMPORAL_CLI_PATH` to a Temporal CLI executable to run the workflow tests. Then run `.\.venv-platform\Scripts\python.exe -m pytest -c pyproject.toml tests/integration`. Set the three OIDC variables in the same PowerShell session before starting the API to make readiness pass.
