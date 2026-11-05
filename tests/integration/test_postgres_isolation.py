"""Run only against a dedicated migrated database and an unprivileged application role."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.main import create_app
from packages.config.settings import Settings
from packages.persistence.database import tenant_transaction
from packages.persistence.models import Agent
from packages.persistence.repository import TenantRepository


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database_url():
    url = os.getenv("PLATFORM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PLATFORM_TEST_DATABASE_URL to a dedicated migrated test database")
    if not url.split("?", 1)[0].endswith("/platform_test"):
        pytest.fail("Integration tests require a database named platform_test")
    return url


@pytest.mark.anyio
async def test_rls_enforces_tenant_boundaries_and_resets_pool_context(database_url):
    engine = create_async_engine(database_url, pool_size=1, max_overflow=0)
    tenant_a, tenant_b, agent_a = uuid4(), uuid4(), uuid4()
    try:
        async with engine.begin() as conn:
            role = (
                await conn.execute(
                    text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).one()
            assert role == (False, False)
        async with tenant_transaction(engine, tenant_a) as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, 'A')"), {"id": tenant_a}
            )
            await conn.execute(
                text("INSERT INTO agents (id, tenant_id, name) VALUES (:id, :tenant, 'agent A')"),
                {"id": agent_a, "tenant": tenant_a},
            )
            assert await TenantRepository(conn, Agent.__table__, tenant_a).get(agent_a) is not None
        async with tenant_transaction(engine, tenant_b) as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, 'B')"), {"id": tenant_b}
            )
            assert (
                await conn.execute(
                    text("SELECT count(*) FROM agents WHERE tenant_id = :tenant"),
                    {"tenant": tenant_a},
                )
            ).scalar_one() == 0
            repo = TenantRepository(conn, Agent.__table__, tenant_b)
            assert await repo.get(agent_a) is None
            result = await conn.execute(
                text("UPDATE agents SET name = 'attacked' WHERE id = :id"), {"id": agent_a}
            )
            assert result.rowcount == 0
            created = await repo.create({"name": "agent B"})
            assert created["tenant_id"] == tenant_b
            with pytest.raises(ValueError):
                await repo.create({"tenant_id": tenant_a, "name": "forbidden"})
            with pytest.raises(DBAPIError) as error:
                await conn.execute(
                    text(
                        "INSERT INTO agents (id, tenant_id, name) "
                        "VALUES (:id, :tenant, 'forbidden')"
                    ),
                    {"id": uuid4(), "tenant": tenant_a},
                )
            assert error.value.orig.sqlstate == "42501"
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM agents"))).scalar_one() == 0
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_agent_version_is_immutable_and_cross_tenant_references_fail(database_url):
    engine = create_async_engine(database_url)
    a, b, agent_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    try:
        async with tenant_transaction(engine, a) as conn:
            await conn.execute(text("INSERT INTO tenants (id, name) VALUES (:id, 'A')"), {"id": a})
            await conn.execute(
                text("INSERT INTO agents (id, tenant_id, name) VALUES (:id, :tenant, 'A')"),
                {"id": agent_id, "tenant": a},
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_versions (id, tenant_id, agent_id, code, prompt, "
                    "model_policy, tool_policy, retrieval_config) "
                    "VALUES (:id, :tenant, :agent, 'sha', 'p', 'm', 't', 'r')"
                ),
                {"id": version_id, "tenant": a, "agent": agent_id},
            )
        async with tenant_transaction(engine, a) as conn:
            with pytest.raises(DBAPIError) as error:
                await conn.execute(
                    text("UPDATE agent_versions SET prompt = 'changed' WHERE id = :id"),
                    {"id": version_id},
                )
            assert error.value.orig.sqlstate == "P0001"
        async with tenant_transaction(engine, b) as conn:
            await conn.execute(text("INSERT INTO tenants (id, name) VALUES (:id, 'B')"), {"id": b})
            with pytest.raises(DBAPIError) as error:
                await conn.execute(
                    text(
                        "INSERT INTO agent_versions (id, tenant_id, agent_id, code, prompt, "
                        "model_policy, tool_policy, retrieval_config) "
                        "VALUES (:id, :tenant, :agent, 'sha', 'p', 'm', 't', 'r')"
                    ),
                    {"id": uuid4(), "tenant": b, "agent": agent_id},
                )
            assert error.value.orig.sqlstate == "23503"
    finally:
        await engine.dispose()


def test_readiness_checks_the_runtime_role_and_rls(database_url):
    class FakeVerifier:
        async def verify(self, token):
            raise AssertionError("not used by readiness")

    app = create_app(Settings(database_url=database_url), verifier=FakeVerifier())
    with TestClient(app) as client:
        assert client.get("/health/ready").json() == {"status": "ok"}
