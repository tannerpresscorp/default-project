# Usage

Phase 7 implements an append-only, tenant-scoped usage ledger. It records token counts and computes cost from an explicit integer price book; it does not enforce budgets, quotas or billing.

- `packages/domain/usage.py`: `ModelPrice` (micro-units per million tokens), `PriceBook`, `UnknownModelPrice` and a default zero-price book for the offline provider.
- `packages/schemas/usage.py`: bounded `UsageRequest`, `UsageRecorded` and `UsageTotals` contracts. Callers cannot submit a cost.
- `packages/persistence/models.py` (`UsageRecord`) and migration `0005_usage`: forced RLS, non-negative checks and tenant-scoped indexes.
- `packages/usage/ledger.py`: `UsageLedger.record` and `UsageLedger.totals`.

Unknown logical models fail closed and write nothing. Prices use integer micro-units so accounting is deterministic; no vendor prices are bundled. Budget enforcement and invoice generation are not implemented.
