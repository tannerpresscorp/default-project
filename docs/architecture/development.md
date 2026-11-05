# Local development

Requires Python 3.12, Docker with Linux containers and the Compose plugin. The original Django environment and pnpm workflow remain unchanged. On Windows use the equivalent `.venv-platform\Scripts\python.exe` instead of `.venv-platform/bin/python`; `make` is optional.

```sh
python3.12 -m venv .venv-platform
.venv-platform/bin/python -m pip install -r requirements-platform-dev.txt
docker compose -f infra/local/compose.yaml up -d --wait postgres redis
export PLATFORM_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform'
export PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@127.0.0.1:55432/platform'
.venv-platform/bin/python -m alembic upgrade head
.venv-platform/bin/python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8001
```

Local database passwords are intentionally public and **only** for this loopback-bound development stack. The migration role is a local superuser; never use it for application traffic. Configure `PLATFORM_OIDC_ISSUER`, `PLATFORM_OIDC_AUDIENCE`, and `PLATFORM_OIDC_JWKS_URL` to use a trusted HTTPS OIDC issuer. The issuer must guarantee the configured UUID tenant claim represents authorized membership for the token subject. Without OIDC configuration, protected endpoints fail closed and readiness reports 503. `PLATFORM_OIDC_TENANT_CLAIM` defaults to `tenant_id`. The app does not issue users, tokens, or tenants.

Health: `GET http://127.0.0.1:8001/health/live`; readiness: `/health/ready`; OpenAPI: `/openapi.json`; authenticated identity: `GET /v1/session` with a bearer token. No tenant header is trusted.

```sh
.venv-platform/bin/python -m ruff check apps packages tests
.venv-platform/bin/python -m ruff format --check apps packages tests
.venv-platform/bin/python -m mypy
.venv-platform/bin/python -m pytest -c pyproject.toml tests/unit
# Dedicated test database; never point this at a shared or production database.
export PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@127.0.0.1:55432/platform_test'
.venv-platform/bin/python -m alembic upgrade head
export PLATFORM_TEST_DATABASE_URL='postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform_test'
.venv-platform/bin/python -m pytest -c pyproject.toml tests/integration
```

The integration tests require the dedicated database name `platform_test` and a non-superuser, non-BYPASSRLS application role. Without its URL pytest reports a skip, not a passing integration verification. They create unique rows and do not clean them up. Run migrations using the migration URL for the target database before testing. `make dev`, `test`, `lint`, `typecheck`, `migrate`, and `integration-test` are equivalent on Unix, with the same environment requirements. Redis is not exercised in Phase 1. Compose data is persistent and is not removed by these commands.

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

For integration tests, point the migration URL at `/platform_test`, migrate that database, and set `PLATFORM_TEST_DATABASE_URL` to the application-role URL ending in `/platform_test`. Then run `.\.venv-platform\Scripts\python.exe -m pytest -c pyproject.toml tests/integration`. Set the three OIDC variables in the same PowerShell session before starting the API to make readiness pass.
