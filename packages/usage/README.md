# Usage and budgets

The package implements an append-only, tenant-scoped usage ledger and optional monthly admission budgets. It records token counts, computes cost from an explicit integer price book and rejects new runs when a configured limit is already exhausted. It does not provide billing or invoices.

- `packages/domain/usage.py`: `ModelPrice` (micro-units per million tokens), `PriceBook`, `UnknownModelPrice` and a default zero-price book for the offline provider.
- `packages/schemas/usage.py`: bounded `UsageRequest`, `UsageRecorded` and `UsageTotals` contracts. Callers cannot submit a cost.
- `packages/schemas/budgets.py`: bounded `BudgetLimits` and `BudgetStatus` contracts. `NULL` limits mean unlimited.
- `packages/persistence/models.py` (`UsageRecord`, `TenantBudget`) and migrations `0005_usage` / `0006_budgets_usage_idempotency`: forced RLS, non-negative checks and tenant-scoped indexes.
- `packages/usage/ledger.py`: `UsageLedger.record` (idempotent per tenant and key) and `UsageLedger.totals`.
- `packages/usage/budget.py`: `BudgetService.status`, `set_limits` and `check`, plus `current_month_start`.

Unknown logical models fail closed and write nothing. Prices use integer micro-units so accounting is deterministic; no vendor prices are bundled. Budget admission control is best-effort and does not interrupt in-flight runs. See [docs/architecture/usage.md](../../docs/architecture/usage.md).
