"""Tenant-scoped usage ledger against PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from packages.domain.usage import ModelPrice, PriceBook, UnknownModelPrice
from packages.persistence.database import tenant_transaction
from packages.schemas.usage import UsageRequest
from packages.usage.ledger import UsageLedger

PRICE_BOOK = PriceBook(
    {"chat": ModelPrice(input_micros_per_million=2_000_000, output_micros_per_million=4_000_000)}
)


async def seed_tenant(engine, tenant_id):
    async with tenant_transaction(engine, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'usage')"), {"id": tenant_id}
        )


@pytest.mark.anyio
async def test_usage_totals_are_tenant_scoped(database_url):
    engine = create_async_engine(database_url)
    tenant_a, tenant_b = uuid4(), uuid4()
    try:
        await seed_tenant(engine, tenant_a)
        await seed_tenant(engine, tenant_b)
        ledger = UsageLedger(engine, PRICE_BOOK)

        first = await ledger.record(
            tenant_a, UsageRequest(logical_model="chat", input_tokens=1_000, output_tokens=500)
        )
        second = await ledger.record(
            tenant_a, UsageRequest(logical_model="chat", input_tokens=0, output_tokens=1_000)
        )

        assert first.cost_micros == 4_000
        assert second.cost_micros == 4_000
        totals = await ledger.totals(tenant_a)
        assert totals.events == 2
        assert totals.input_tokens == 1_000
        assert totals.output_tokens == 1_500
        assert totals.cost_micros == 8_000
        assert (await ledger.totals(tenant_b)).events == 0

        async with tenant_transaction(engine, tenant_b) as conn:
            visible = (await conn.execute(text("SELECT count(*) FROM usage_records"))).scalar_one()
        assert visible == 0
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_usage_can_be_filtered_by_logical_model(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        ledger = UsageLedger(engine, PRICE_BOOK)
        await ledger.record(
            tenant_id, UsageRequest(logical_model="chat", input_tokens=10, output_tokens=10)
        )

        totals = await ledger.totals(tenant_id, logical_model="chat")
        missing = await ledger.totals(tenant_id, logical_model="embedding")

        assert totals.events == 1
        assert missing.events == 0
        assert missing.cost_micros == 0
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_unknown_pricing_does_not_write_a_record(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    try:
        await seed_tenant(engine, tenant_id)
        ledger = UsageLedger(engine, PRICE_BOOK)

        with pytest.raises(UnknownModelPrice):
            await ledger.record(
                tenant_id,
                UsageRequest(logical_model="unpriced", input_tokens=1, output_tokens=1),
            )

        assert (await ledger.totals(tenant_id)).events == 0
    finally:
        await engine.dispose()
