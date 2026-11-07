# Usage accounting and budgets

The platform has an append-only, tenant-scoped token ledger and optional monthly admission budgets. It records usage for governed model calls, exposes tenant totals and rejects new runs when a configured limit is already exhausted. It does not produce invoices.

## Pricing

`ModelPrice` stores input and output prices as integer micro-units (1 USD = 1,000,000) per million tokens. `cost_micros` rounds up, so a positive price never becomes free through truncation. `PriceBook` fails closed for an unconfigured logical model; the default book prices only the offline `chat` and `embedding` models at zero and makes no vendor-cost claim.

Callers submit token counts only. `UsageLedger` computes the cost server-side, so a client cannot choose its own price.

## Persistence

`usage_records` stores `tenant_id`, optional `run_id`, an optional `idempotency_key`, logical model, token counts, computed cost and timestamp. The table uses forced RLS with read and write checks, a non-negative check constraint, and tenant-scoped indexes. `run_id` is a reference without a foreign key so usage can be recorded even for a run that was never persisted. A partial unique index on `(tenant_id, idempotency_key)` makes activity retries safe: recording the same key returns the original row. The workflow worker uses `run:<run_id>` as the key.

`tenant_budgets` stores one optional row per tenant with nullable `monthly_cost_micros` and `monthly_tokens` limits, forced RLS and a non-negative check. `NULL` means unlimited, so a tenant with no row is unconstrained.

## Enforcement

`BudgetService` computes the current UTC calendar-month totals and compares them with the configured limits:

- cost blocks when `cost_micros >= monthly_cost_micros`;
- tokens block when `input_tokens + output_tokens >= monthly_tokens`;
- an absent limit never blocks.

`POST /v1/runs` checks the budget before creating a row and returns 429 when exhausted; `GET` and `PUT /v1/budget` read or replace the limits. This is best-effort admission control, not a reservation: concurrent submissions and work already in flight can overshoot a limit. Moving usage into a previous month releases the current month automatically.

## Not implemented

There is no reservation, hard quota that interrupts an in-flight run, rate limiting, invoice export, price versioning, currency conversion or reconciliation against vendor invoices. Reporting uses simple SQL aggregates inside the tenant transaction.
