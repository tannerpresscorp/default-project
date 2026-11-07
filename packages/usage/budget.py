"""Tenant monthly admission budgets.

Limits are optional and apply to the current UTC calendar month. Admission is
checked before a run is submitted; an absent limit means unlimited. This is
best-effort admission control, not a reservation system: concurrent submissions
can overshoot a limit by the work already in flight.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from packages.persistence.database import tenant_transaction
from packages.persistence.repository import TenantBudgetRepository, UsageRepository
from packages.schemas.budgets import BudgetLimits, BudgetStatus


class BudgetExceeded(RuntimeError):
    """The tenant has consumed its current-month allowance."""

    def __init__(self) -> None:
        super().__init__("tenant budget exhausted")


def current_month_start(now: datetime | None = None) -> datetime:
    """Return the first instant of the current UTC month."""
    now = now or datetime.now(UTC)
    return now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class BudgetService:
    """Read, update and enforce one tenant's monthly token and cost limits."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def status(self, tenant_id: UUID) -> BudgetStatus:
        since = current_month_start()
        async with tenant_transaction(self._engine, tenant_id) as conn:
            budget = await TenantBudgetRepository(conn, tenant_id).get_for_tenant()
            totals = await UsageRepository(conn, tenant_id).totals(since=since)
        return BudgetStatus(
            monthly_cost_micros=budget["monthly_cost_micros"] if budget else None,
            monthly_tokens=budget["monthly_tokens"] if budget else None,
            events=totals["events"],
            input_tokens=totals["input_tokens"],
            output_tokens=totals["output_tokens"],
            cost_micros=totals["cost_micros"],
        )

    async def set_limits(self, tenant_id: UUID, limits: BudgetLimits) -> BudgetStatus:
        async with tenant_transaction(self._engine, tenant_id) as conn:
            await TenantBudgetRepository(conn, tenant_id).set_limits(
                monthly_cost_micros=limits.monthly_cost_micros,
                monthly_tokens=limits.monthly_tokens,
            )
        return await self.status(tenant_id)

    async def check(self, tenant_id: UUID) -> None:
        status = await self.status(tenant_id)
        used_tokens = status.input_tokens + status.output_tokens
        if (
            status.monthly_cost_micros is not None
            and status.cost_micros >= status.monthly_cost_micros
        ):
            raise BudgetExceeded()
        if status.monthly_tokens is not None and used_tokens >= status.monthly_tokens:
            raise BudgetExceeded()
