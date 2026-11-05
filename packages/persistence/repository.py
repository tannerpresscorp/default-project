from typing import Any
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


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
