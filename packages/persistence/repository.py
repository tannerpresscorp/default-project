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
from packages.persistence.models import AgentRun


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
