"""Audited, idempotent tool invocation against PostgreSQL."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from apps.tool_gateway.errors import (
    ToolApprovalRequired,
    ToolExecutionError,
    ToolGatewayError,
    ToolInvocationError,
)
from apps.tool_gateway.gateway import ToolGateway
from apps.tool_gateway.invocations import ToolInvocationService, arguments_digest
from apps.tool_gateway.registry import InMemoryToolRegistry
from packages.domain.tools import ApprovalStatus, InvocationStatus
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import (
    ToolApprovalRepository,
    ToolInvocationRepository,
)
from packages.policies.tools import AllowlistToolPolicy
from packages.schemas.tools import ToolDefinition

SCHEMA = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}


class FakeTool:
    def __init__(
        self,
        name: str,
        *,
        requires_approval: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.definition = ToolDefinition(
            name=name,
            description=f"{name} tool",
            input_schema=SCHEMA,
            requires_approval=requires_approval,
        )
        self.calls: list[dict[str, Any]] = []
        self._error = error

    async def invoke(self, arguments: dict[str, Any]) -> Any:
        self.calls.append(dict(arguments))
        if self._error is not None:
            raise self._error
        return {"echo": arguments["city"]}


async def seed_tenant(engine, tenant_id):
    async with tenant_transaction(engine, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'tools')"), {"id": tenant_id}
        )


def service_for(engine, tools, tenant_id):
    gateway = ToolGateway(
        InMemoryToolRegistry(tools),
        AllowlistToolPolicy({tenant_id: frozenset(tool.definition.name for tool in tools)}),
    )
    return ToolInvocationService(engine, gateway)


@pytest.mark.anyio
async def test_idempotent_invocation_replays_without_executing_twice(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        tool = FakeTool("lookup")
        service = service_for(engine, [tool], tenant_id)
        arguments = {"city": "Paris"}
        key = f"key-{uuid4()}"

        first = await service.invoke(tenant_id, "lookup", arguments, idempotency_key=key)
        second = await service.invoke(tenant_id, "lookup", arguments, idempotency_key=key)

        assert first.content == {"echo": "Paris"}
        assert second == first
        assert tool.calls == [arguments]

        async with tenant_transaction(engine, tenant_id) as conn:
            row = await ToolInvocationRepository(conn, tenant_id).by_idempotency_key(key)
        assert row is not None
        assert row["status"] == InvocationStatus.SUCCEEDED.value
        assert row["result"] == {"echo": "Paris"}
        assert row["arguments_digest"] == arguments_digest(arguments)
        assert row["error_code"] is None

        with pytest.raises(ToolInvocationError):
            await service.invoke(tenant_id, "lookup", {"city": "Rome"}, idempotency_key=key)
        assert len(tool.calls) == 1
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_failure_is_audited_without_arguments_or_messages(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        tool = FakeTool("broken", error=RuntimeError("password=hunter2"))
        service = service_for(engine, [tool], tenant_id)

        with pytest.raises(ToolExecutionError):
            await service.invoke(tenant_id, "broken", {"city": "Paris"})

        async with tenant_transaction(engine, tenant_id) as conn:
            row = (
                (
                    await conn.execute(
                        text("SELECT status, error_code, result FROM tool_invocations")
                    )
                )
                .mappings()
                .one()
            )
        assert row["status"] == InvocationStatus.FAILED.value
        assert row["error_code"] == "ToolExecutionError"
        assert row["result"] is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_approval_is_required_and_tenant_scoped(database_url):
    engine = create_async_engine(database_url)
    tenant_a, tenant_b = uuid4(), uuid4()
    try:
        await seed_tenant(engine, tenant_a)
        await seed_tenant(engine, tenant_b)
        tool = FakeTool("delete_account", requires_approval=True)
        service_a = service_for(engine, [tool], tenant_a)
        service_b = service_for(engine, [tool], tenant_b)

        with pytest.raises(ToolApprovalRequired):
            await service_a.invoke(tenant_a, "delete_account", {"city": "Paris"})
        assert tool.calls == []

        approval_id = uuid4()
        async with tenant_transaction(engine, tenant_a) as conn:
            repo = ToolApprovalRepository(conn, tenant_a)
            await repo.request(
                approval_id=approval_id,
                tool_name="delete_account",
                arguments_digest=arguments_digest({"city": "Paris"}),
                requested_by="runner",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            await repo.decide(approval_id, status=ApprovalStatus.APPROVED, decided_by="operator")

        with pytest.raises(ToolApprovalRequired):
            await service_b.invoke(
                tenant_b, "delete_account", {"city": "Paris"}, approval_id=approval_id
            )
        assert tool.calls == []

        result = await service_a.invoke(
            tenant_a, "delete_account", {"city": "Paris"}, approval_id=approval_id
        )
        assert result.content == {"echo": "Paris"}
        assert tool.calls == [{"city": "Paris"}]

        async with tenant_transaction(engine, tenant_b) as conn:
            visible = (await conn.execute(text("SELECT count(*) FROM tool_approvals"))).scalar_one()
        assert visible == 0
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_denied_invocation_is_audited(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        tool = FakeTool("allowed")
        gateway = ToolGateway(
            InMemoryToolRegistry([tool]), AllowlistToolPolicy({tenant_id: frozenset()})
        )
        service = ToolInvocationService(engine, gateway)

        with pytest.raises(ToolGatewayError):
            await service.invoke(tenant_id, "allowed", {"city": "Paris"})

        async with tenant_transaction(engine, tenant_id) as conn:
            row = (
                (await conn.execute(text("SELECT status, error_code FROM tool_invocations")))
                .mappings()
                .one()
            )
        assert row["status"] == InvocationStatus.DENIED.value
        assert row["error_code"] == "ToolNotAllowed"
    finally:
        await engine.dispose()
