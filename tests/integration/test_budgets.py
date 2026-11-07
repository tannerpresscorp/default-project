"""Monthly tenant budgets and idempotent usage against PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from packages.domain.usage import ModelPrice, PriceBook
from packages.persistence.database import tenant_transaction
from packages.schemas.budgets import BudgetLimits
from packages.schemas.usage import UsageRequest
from packages.usage.budget import BudgetExceeded, BudgetService
from packages.usage.ledger import UsageLedger

PRICE_BOOK = PriceBook(
    {"chat": ModelPrice(input_micros_per_million=2_000_000, output_micros_per_million=4_000_000)}
)


async def seed_tenant(engine, tenant_id):
    async with tenant_transaction(engine, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'budget')"), {"id": tenant_id}
        )


@pytest.mark.anyio
async def test_idempotent_usage_recording_returns_the_original_row(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        ledger = UsageLedger(engine, PRICE_BOOK)
        request = UsageRequest(
            logical_model="chat",
            input_tokens=10,
            output_tokens=5,
            idempotency_key="run:fixed",
        )

        first = await ledger.record(tenant_id, request)
        second = await ledger.record(tenant_id, request)

        assert first.id == second.id
        assert (await ledger.totals(tenant_id)).events == 1
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_budget_status_uses_limits_and_current_month_usage(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        ledger = UsageLedger(engine, PRICE_BOOK)
        budgets = BudgetService(engine)

        initial = await budgets.status(tenant_id)
        assert initial.monthly_cost_micros is None
        assert initial.monthly_tokens is None
        assert initial.events == 0

        limits = await budgets.set_limits(
            tenant_id, BudgetLimits(monthly_cost_micros=4_000, monthly_tokens=1_500)
        )
        assert limits.monthly_cost_micros == 4_000
        assert limits.monthly_tokens == 1_500

        recorded = await ledger.record(
            tenant_id,
            UsageRequest(logical_model="chat", input_tokens=1_000, output_tokens=500),
        )
        assert recorded.cost_micros == 4_000

        status = await budgets.status(tenant_id)
        assert status.events == 1
        assert status.input_tokens == 1_000
        assert status.output_tokens == 500
        assert status.cost_micros == 4_000

        with pytest.raises(BudgetExceeded):
            await budgets.check(tenant_id)

        await budgets.set_limits(
            tenant_id, BudgetLimits(monthly_cost_micros=4_001, monthly_tokens=1_501)
        )
        await budgets.check(tenant_id)

        async with tenant_transaction(engine, tenant_id) as conn:
            await conn.execute(
                text("UPDATE usage_records SET created_at = now() - interval '40 days'")
            )
        assert (await budgets.status(tenant_id)).events == 0
        await budgets.check(tenant_id)

        other = await budgets.status(uuid4())
        assert other.monthly_tokens is None
    finally:
        await engine.dispose()
