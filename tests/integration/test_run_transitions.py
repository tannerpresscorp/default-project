"""Durable agent-run state transitions against a migrated PostgreSQL database."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from packages.domain.runs import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    InvalidRunTransition,
    RunStatus,
)
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import (
    AgentRunNotFound,
    AgentRunRepository,
    AgentRunStateConflict,
)


async def seed_agent(engine: AsyncEngine, tenant_id: UUID) -> tuple[UUID, UUID]:
    agent_id, version_id = uuid4(), uuid4()
    async with tenant_transaction(engine, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'tenant')"), {"id": tenant_id}
        )
        await conn.execute(
            text("INSERT INTO agents (id, tenant_id, name) VALUES (:id, :tenant, 'agent')"),
            {"id": agent_id, "tenant": tenant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO agent_versions (id, tenant_id, agent_id, code, prompt, "
                "model_policy, tool_policy, retrieval_config) "
                "VALUES (:id, :tenant, :agent, 'sha', 'p', 'm', 't', 'r')"
            ),
            {"id": version_id, "tenant": tenant_id, "agent": agent_id},
        )
    return agent_id, version_id


async def create_run(
    engine: AsyncEngine, tenant_id: UUID, agent_id: UUID, version_id: UUID
) -> dict:
    async with tenant_transaction(engine, tenant_id) as conn:
        row = await AgentRunRepository(conn, tenant_id).create(
            {"agent_id": agent_id, "agent_version_id": version_id}
        )
        return dict(row)


async def _attempt_transition(
    conn: AsyncConnection, run_id: UUID, target: RunStatus
) -> tuple[bool, int | DBAPIError]:
    """Run one direct SQL transition inside a savepoint so failures stay isolated."""
    finished_at = datetime.now(UTC) if target in TERMINAL_STATUSES else None
    try:
        async with conn.begin_nested():
            result = await conn.execute(
                text(
                    "UPDATE agent_runs SET status = :status, finished_at = :finished WHERE id = :id"
                ),
                {"status": target.value, "finished": finished_at, "id": run_id},
            )
            return True, result.rowcount
    except DBAPIError as error:
        return False, error


@pytest.mark.anyio
async def test_run_lifecycle_records_timestamps_and_terminal_state(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        agent_id, version_id = await seed_agent(engine, tenant_id)
        async with tenant_transaction(engine, tenant_id) as conn:
            repo = AgentRunRepository(conn, tenant_id)
            with pytest.raises(ValueError):
                await repo.create(
                    {
                        "agent_id": agent_id,
                        "agent_version_id": version_id,
                        "status": RunStatus.RUNNING,
                    }
                )
            run = await repo.create({"agent_id": agent_id, "agent_version_id": version_id})
            assert run["status"] == RunStatus.PENDING.value
            assert run["started_at"] is None
            assert run["finished_at"] is None

            run = await repo.transition(
                run["id"], expected=RunStatus.PENDING, target=RunStatus.RUNNING
            )
            started_at = run["started_at"]
            assert run["status"] == RunStatus.RUNNING.value
            assert started_at is not None
            assert run["finished_at"] is None

            run = await repo.transition(
                run["id"], expected=RunStatus.RUNNING, target=RunStatus.WAITING_FOR_TOOL
            )
            run = await repo.transition(
                run["id"], expected=RunStatus.WAITING_FOR_TOOL, target=RunStatus.RUNNING
            )
            assert run["started_at"] == started_at

            run = await repo.transition(
                run["id"], expected=RunStatus.RUNNING, target=RunStatus.SUCCEEDED
            )
            assert run["status"] == RunStatus.SUCCEEDED.value
            assert run["finished_at"] is not None
            assert run["updated_at"] >= run["created_at"]

            with pytest.raises(InvalidRunTransition):
                await repo.transition(
                    run["id"], expected=RunStatus.SUCCEEDED, target=RunStatus.RUNNING
                )
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_stale_expected_state_is_a_conflict_and_changes_nothing(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        agent_id, version_id = await seed_agent(engine, tenant_id)
        run = await create_run(engine, tenant_id, agent_id, version_id)
        async with tenant_transaction(engine, tenant_id) as conn:
            await AgentRunRepository(conn, tenant_id).transition(
                run["id"], expected=RunStatus.PENDING, target=RunStatus.RUNNING
            )

        with pytest.raises(AgentRunStateConflict) as error:
            async with tenant_transaction(engine, tenant_id) as conn:
                await AgentRunRepository(conn, tenant_id).transition(
                    run["id"], expected=RunStatus.PENDING, target=RunStatus.CANCELLED
                )
        assert error.value.expected is RunStatus.PENDING
        assert error.value.actual is RunStatus.RUNNING

        async with tenant_transaction(engine, tenant_id) as conn:
            stored = await AgentRunRepository(conn, tenant_id).get(run["id"])
        assert stored is not None
        assert stored["status"] == RunStatus.RUNNING.value
        assert stored["finished_at"] is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_cross_tenant_run_access_is_not_found(database_url):
    engine = create_async_engine(database_url)
    tenant_a, tenant_b = uuid4(), uuid4()
    try:
        agent_id, version_id = await seed_agent(engine, tenant_a)
        run = await create_run(engine, tenant_a, agent_id, version_id)
        async with tenant_transaction(engine, tenant_b) as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, 'other')"), {"id": tenant_b}
            )
            repo = AgentRunRepository(conn, tenant_b)
            assert await repo.get(run["id"]) is None
            with pytest.raises(AgentRunNotFound):
                await repo.transition(
                    run["id"], expected=RunStatus.PENDING, target=RunStatus.RUNNING
                )
            result = await conn.execute(
                text("UPDATE agent_runs SET status = 'RUNNING' WHERE id = :id"), {"id": run["id"]}
            )
            assert result.rowcount == 0

        async with tenant_transaction(engine, tenant_a) as conn:
            stored = await AgentRunRepository(conn, tenant_a).get(run["id"])
        assert stored is not None
        assert stored["status"] == RunStatus.PENDING.value
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_database_rejects_invalid_status_and_direct_transition_bypass(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        agent_id, version_id = await seed_agent(engine, tenant_id)
        run = await create_run(engine, tenant_id, agent_id, version_id)

        with pytest.raises(DBAPIError) as error:
            async with tenant_transaction(engine, tenant_id) as conn:
                await conn.execute(
                    text(
                        "INSERT INTO agent_runs "
                        "(id, tenant_id, agent_id, agent_version_id, status) "
                        "VALUES (:id, :tenant, :agent, :version, 'UNKNOWN')"
                    ),
                    {
                        "id": uuid4(),
                        "tenant": tenant_id,
                        "agent": agent_id,
                        "version": version_id,
                    },
                )
        assert error.value.orig.sqlstate == "23514"

        with pytest.raises(DBAPIError) as error:
            async with tenant_transaction(engine, tenant_id) as conn:
                await conn.execute(
                    text("UPDATE agent_runs SET status = 'WAITING_FOR_TOOL' WHERE id = :id"),
                    {"id": run["id"]},
                )
        assert error.value.orig.sqlstate == "P0001"

        async with tenant_transaction(engine, tenant_id) as conn:
            stored = await AgentRunRepository(conn, tenant_id).get(run["id"])
        assert stored is not None
        assert stored["status"] == RunStatus.PENDING.value
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_database_transition_map_matches_the_domain(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        agent_id, version_id = await seed_agent(engine, tenant_id)
        async with tenant_transaction(engine, tenant_id) as conn:
            runs: dict[tuple[RunStatus, RunStatus], UUID] = {}
            for current in RunStatus:
                for target in RunStatus:
                    run_id = uuid4()
                    finished_at = datetime.now(UTC) if current in TERMINAL_STATUSES else None
                    await conn.execute(
                        text(
                            "INSERT INTO agent_runs "
                            "(id, tenant_id, agent_id, agent_version_id, status, finished_at) "
                            "VALUES (:id, :tenant, :agent, :version, :status, :finished)"
                        ),
                        {
                            "id": run_id,
                            "tenant": tenant_id,
                            "agent": agent_id,
                            "version": version_id,
                            "status": current.value,
                            "finished": finished_at,
                        },
                    )
                    runs[(current, target)] = run_id

            for (current, target), run_id in runs.items():
                if current == target:
                    continue
                allowed = target in ALLOWED_TRANSITIONS[current]
                succeeded, outcome = await _attempt_transition(conn, run_id, target)
                assert succeeded is allowed, f"{current} -> {target}"
                if allowed:
                    assert outcome == 1
                else:
                    assert isinstance(outcome, DBAPIError)
                    assert outcome.orig.sqlstate == "P0001"
    finally:
        await engine.dispose()
