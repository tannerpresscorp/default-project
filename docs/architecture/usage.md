# Usage accounting

Phase 7 implements an append-only, tenant-scoped token ledger. It records usage for governed model calls and exposes tenant totals; it does not enforce budgets or produce invoices.

## Pricing

`ModelPrice` stores input and output prices as integer micro-units (1 USD = 1,000,000) per million tokens. `cost_micros` rounds up, so a positive price never becomes free through truncation. `PriceBook` fails closed for an unconfigured logical model; the default book prices only the offline `chat` and `embedding` models at zero and makes no vendor-cost claim.

Callers submit token counts only. `UsageLedger` computes the cost server-side, so a client cannot choose its own price.

## Persistence

`usage_records` stores `tenant_id`, optional `run_id`, logical model, token counts, computed cost and timestamp. The table uses forced RLS with read and write checks, a non-negative check constraint, and tenant-scoped indexes. `run_id` is a reference without a foreign key so usage can be recorded even for a run that was never persisted.

## Not implemented

There is no budget reservation, quota rejection, rate limiting, invoice export, price versioning, currency conversion or reconciliation against vendor invoices. Reporting uses simple SQL aggregates inside the tenant transaction.
