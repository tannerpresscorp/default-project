"""Append-only usage ledger with deterministic pricing and tenant isolation."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

from packages.domain.usage import DEFAULT_PRICE_BOOK, PriceBook
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import UsageRepository
from packages.schemas.usage import UsageRecorded, UsageRequest, UsageTotals


class UsageLedger:
    """Record token usage and read tenant totals; no budget enforcement yet."""

    def __init__(self, engine: AsyncEngine, price_book: PriceBook = DEFAULT_PRICE_BOOK) -> None:
        self._engine = engine
        self._price_book = price_book

    async def record(self, tenant_id: UUID, request: UsageRequest) -> UsageRecorded:
        price = self._price_book.price(request.logical_model)
        cost_micros = price.cost_micros(request.input_tokens, request.output_tokens)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            row = await UsageRepository(conn, tenant_id).record(
                logical_model=request.logical_model,
                input_tokens=request.input_tokens,
                output_tokens=request.output_tokens,
                cost_micros=cost_micros,
                run_id=request.run_id,
            )
        return UsageRecorded(
            id=row["id"],
            logical_model=row["logical_model"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_micros=row["cost_micros"],
        )

    async def totals(self, tenant_id: UUID, *, logical_model: str | None = None) -> UsageTotals:
        async with tenant_transaction(self._engine, tenant_id) as conn:
            row = await UsageRepository(conn, tenant_id).totals(logical_model=logical_model)
        return UsageTotals(
            events=row["events"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_micros=row["cost_micros"],
        )
