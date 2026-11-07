from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, func, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.domain.runs import (
    TERMINAL_STATUSES,
    RunStatus,
    ensure_transition,
)
from packages.domain.tools import ApprovalStatus, InvocationStatus
from packages.persistence.models import AgentRun, ToolApproval, ToolInvocation, UsageRecord


class TenantRepository:
    """All operations require an already tenant-bound transaction."""

    def __init__(self, conn: AsyncConnection, table: Table, tenant_id: UUID):
        if "tenant_id" not in table.c:
            raise ValueError("Repository requires a tenant-owned table")
        self._conn, self._table, self._tenant_id = conn, table, tenant_id

    async def get(self, resource_id: UUID) -> RowMapping | None:
        stmt = select(self._table).where(
            self._table.c.tenant_id == self._tenant_id, self._table.c.id == resource_id
        )
        return (await self._conn.execute(stmt)).mappings().one_or_none()

    async def create(self, values: dict[str, Any]) -> RowMapping:
        if "tenant_id" in values:
            raise ValueError("tenant_id must come from authenticated context")
        stmt = (
            self._table.insert()
            .values(**values, tenant_id=self._tenant_id)
            .returning(*self._table.c)
        )
        return (await self._conn.execute(stmt)).mappings().one()


class AgentRunNotFound(LookupError):
    """The run does not exist inside the caller's tenant boundary."""

    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        super().__init__(f"agent run {run_id} not found")


class AgentRunStateConflict(RuntimeError):
    """The run is no longer in the state the caller expected."""

    def __init__(self, run_id: UUID, expected: RunStatus, actual: RunStatus) -> None:
        self.run_id = run_id
        self.expected = expected
        self.actual = actual
        super().__init__(f"agent run {run_id} is {actual}, expected {expected}")


class AgentRunRepository(TenantRepository):
    """Tenant-scoped durable state for agent runs."""

    def __init__(self, conn: AsyncConnection, tenant_id: UUID) -> None:
        super().__init__(conn, cast(Table, AgentRun.__table__), tenant_id)

    async def create(self, values: dict[str, Any]) -> RowMapping:
        if values.get("status", RunStatus.PENDING) != RunStatus.PENDING:
            raise ValueError("agent runs must be created in PENDING state")
        return await super().create(values)

    async def transition(
        self, run_id: UUID, *, expected: RunStatus, target: RunStatus
    ) -> RowMapping:
        ensure_transition(expected, target)
        values: dict[str, Any] = {
            "status": target.value,
            "updated_at": func.now(),
            "finished_at": func.now() if target in TERMINAL_STATUSES else None,
        }
        if target is RunStatus.RUNNING:
            values["started_at"] = func.coalesce(self._table.c.started_at, func.now())
        stmt = (
            update(self._table)
            .where(
                self._table.c.tenant_id == self._tenant_id,
                self._table.c.id == run_id,
                self._table.c.status == expected.value,
            )
            .values(**values)
            .returning(*self._table.c)
        )
        row = (await self._conn.execute(stmt)).mappings().one_or_none()
        if row is not None:
            return row
        existing = await self.get(run_id)
        if existing is None:
            raise AgentRunNotFound(run_id)
        raise AgentRunStateConflict(run_id, expected, RunStatus(existing["status"]))


class ToolInvocationNotFound(LookupError):
    """The invocation does not exist inside the caller's tenant boundary."""

    def __init__(self, invocation_id: UUID) -> None:
        self.invocation_id = invocation_id
        super().__init__(f"tool invocation {invocation_id} not found")


class ToolInvocationStateConflict(RuntimeError):
    """The invocation is no longer STARTED."""

    def __init__(self, invocation_id: UUID) -> None:
        self.invocation_id = invocation_id
        super().__init__(f"tool invocation {invocation_id} is already finished")


class ToolInvocationRepository(TenantRepository):
    """Tenant-scoped audit records and idempotency reservations."""

    def __init__(self, conn: AsyncConnection, tenant_id: UUID) -> None:
        super().__init__(conn, cast(Table, ToolInvocation.__table__), tenant_id)

    async def start(
        self,
        *,
        tool_name: str,
        arguments_digest: str,
        idempotency_key: str | None,
    ) -> RowMapping:
        return await self.create(
            {
                "tool_name": tool_name,
                "arguments_digest": arguments_digest,
                "idempotency_key": idempotency_key,
                "status": InvocationStatus.STARTED.value,
            }
        )

    async def by_idempotency_key(self, idempotency_key: str) -> RowMapping | None:
        stmt = select(self._table).where(
            self._table.c.tenant_id == self._tenant_id,
            self._table.c.idempotency_key == idempotency_key,
        )
        return (await self._conn.execute(stmt)).mappings().one_or_none()

    async def finish(
        self,
        invocation_id: UUID,
        *,
        status: InvocationStatus,
        result: Any | None = None,
        error_code: str | None = None,
    ) -> RowMapping:
        if status not in {
            InvocationStatus.SUCCEEDED,
            InvocationStatus.FAILED,
            InvocationStatus.DENIED,
        }:
            raise ValueError("invocations must finish in a terminal state")
        stmt = (
            update(self._table)
            .where(
                self._table.c.tenant_id == self._tenant_id,
                self._table.c.id == invocation_id,
                self._table.c.status == InvocationStatus.STARTED.value,
            )
            .values(
                status=status.value,
                result=result,
                error_code=error_code,
                finished_at=func.now(),
            )
            .returning(*self._table.c)
        )
        row = (await self._conn.execute(stmt)).mappings().one_or_none()
        if row is not None:
            return row
        if await self.get(invocation_id) is None:
            raise ToolInvocationNotFound(invocation_id)
        raise ToolInvocationStateConflict(invocation_id)


class ToolApprovalNotFound(LookupError):
    """The approval does not exist inside the caller's tenant boundary."""

    def __init__(self, approval_id: UUID) -> None:
        self.approval_id = approval_id
        super().__init__(f"tool approval {approval_id} not found")


class ToolApprovalStateConflict(RuntimeError):
    """The approval is no longer PENDING."""

    def __init__(self, approval_id: UUID) -> None:
        self.approval_id = approval_id
        super().__init__(f"tool approval {approval_id} is already decided")


class ToolApprovalRepository(TenantRepository):
    """Tenant-scoped durable approvals for tools that require human consent."""

    def __init__(self, conn: AsyncConnection, tenant_id: UUID) -> None:
        super().__init__(conn, cast(Table, ToolApproval.__table__), tenant_id)

    async def request(
        self,
        *,
        tool_name: str,
        arguments_digest: str,
        requested_by: str,
        expires_at: datetime,
        approval_id: UUID | None = None,
    ) -> RowMapping:
        values: dict[str, Any] = {
            "tool_name": tool_name,
            "arguments_digest": arguments_digest,
            "requested_by": requested_by,
            "expires_at": expires_at,
            "status": ApprovalStatus.PENDING.value,
        }
        if approval_id is not None:
            values["id"] = approval_id
        return await self.create(values)

    async def find_approved(self, tool_name: str, arguments_digest: str) -> RowMapping | None:
        stmt = select(self._table).where(
            self._table.c.tenant_id == self._tenant_id,
            self._table.c.tool_name == tool_name,
            self._table.c.arguments_digest == arguments_digest,
            self._table.c.status == ApprovalStatus.APPROVED.value,
            self._table.c.expires_at > func.now(),
        )
        return (await self._conn.execute(stmt)).mappings().one_or_none()

    async def decide(
        self,
        approval_id: UUID,
        *,
        status: ApprovalStatus,
        decided_by: str,
    ) -> RowMapping:
        if status not in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED}:
            raise ValueError("approvals must be approved or denied")
        stmt = (
            update(self._table)
            .where(
                self._table.c.tenant_id == self._tenant_id,
                self._table.c.id == approval_id,
                self._table.c.status == ApprovalStatus.PENDING.value,
            )
            .values(status=status.value, decided_by=decided_by, decided_at=func.now())
            .returning(*self._table.c)
        )
        row = (await self._conn.execute(stmt)).mappings().one_or_none()
        if row is not None:
            return row
        if await self.get(approval_id) is None:
            raise ToolApprovalNotFound(approval_id)
        raise ToolApprovalStateConflict(approval_id)

    async def expire(self, approval_id: UUID) -> RowMapping:
        stmt = (
            update(self._table)
            .where(
                self._table.c.tenant_id == self._tenant_id,
                self._table.c.id == approval_id,
                self._table.c.status == ApprovalStatus.PENDING.value,
            )
            .values(status=ApprovalStatus.EXPIRED.value, decided_at=func.now())
            .returning(*self._table.c)
        )
        row = (await self._conn.execute(stmt)).mappings().one_or_none()
        if row is not None:
            return row
        if await self.get(approval_id) is None:
            raise ToolApprovalNotFound(approval_id)
        raise ToolApprovalStateConflict(approval_id)


class UsageRepository(TenantRepository):
    """Append-only tenant usage records and aggregate reads."""

    def __init__(self, conn: AsyncConnection, tenant_id: UUID) -> None:
        super().__init__(conn, cast(Table, UsageRecord.__table__), tenant_id)

    async def record(
        self,
        *,
        logical_model: str,
        input_tokens: int,
        output_tokens: int,
        cost_micros: int,
        run_id: UUID | None,
    ) -> RowMapping:
        return await self.create(
            {
                "logical_model": logical_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_micros": cost_micros,
                "run_id": run_id,
            }
        )

    async def totals(self, *, logical_model: str | None = None) -> RowMapping:
        stmt = select(
            func.count().label("events"),
            func.coalesce(func.sum(self._table.c.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(self._table.c.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(self._table.c.cost_micros), 0).label("cost_micros"),
        ).where(self._table.c.tenant_id == self._tenant_id)
        if logical_model is not None:
            stmt = stmt.where(self._table.c.logical_model == logical_model)
        return (await self._conn.execute(stmt)).mappings().one()
