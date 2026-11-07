# Agent runtime

The runtime is split into a durable PostgreSQL state machine and deterministic Temporal workflows. PostgreSQL is authoritative for run status, timestamps and approvals; Temporal owns retries, timers and recovery. External effects (database writes and model calls) run only in activities, and interactive requests are never the only copy of critical state. No runtime HTTP API, streaming, budgets or cancellation endpoint exists yet.

## Temporal workflows

`apps/workflow_worker/` contains the worker, workflow and activity definitions:

- `AgentRunWorkflow` performs `agent_run.start` → `agent_run.generate` → `agent_run.complete`. If generation or completion fails, it runs `agent_run.fail` before re-raising so the persisted run reaches `FAILED` instead of remaining `RUNNING`.
- `ToolApprovalWorkflow` creates a durable approval record, waits on a `decide` signal with a bounded timer, then persists `APPROVED` or `DENIED`. A timeout persists `EXPIRED` and fails the workflow.
- Workflow modules import no database, HTTP or model-client libraries. All non-deterministic work is in `activities.py`, which keeps every query inside `tenant_transaction`.

Activity retries are bounded (`maximum_attempts=3`) with a 30-second start-to-close timeout. Configuration is `PLATFORM_TEMPORAL_ADDRESS` (required for the worker), `PLATFORM_TEMPORAL_NAMESPACE` (default `default`) and `PLATFORM_TEMPORAL_TASK_QUEUE` (default `agent-runs`). The worker requires `PLATFORM_DATABASE_URL`. Only the deterministic offline model provider is wired; the worker makes no vendor calls.

## States

`PENDING`, `RUNNING`, `WAITING_FOR_TOOL`, `WAITING_FOR_APPROVAL`, `RETRYING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `TIMED_OUT`.

`SUCCEEDED`, `FAILED`, `CANCELLED` and `TIMED_OUT` are terminal and have no outgoing transitions. A run starts in `PENDING`; application code cannot create it in another state. Transition rules live in `packages/domain/runs.py` and are the contract for both application code and the database.

## Persistence

`AgentRunRepository` is tenant-scoped and operates only inside `tenant_transaction`. `transition(run_id, expected=..., target=...)`:

- rejects a transition outside the state machine before touching the database;
- updates only when the stored status still equals `expected`, so concurrent callers cannot overwrite a newer state;
- sets `updated_at`, records the first `started_at` when entering `RUNNING`, and sets `finished_at` on terminal states;
- raises `AgentRunNotFound` when the run is absent inside the caller's tenant and `AgentRunStateConflict` when the stored state differs from `expected`.

Cross-tenant identifiers are indistinguishable from missing rows. The composite tenant foreign keys and forced RLS policies remain the isolation boundary.

## Database enforcement

Migration `0002_agent_run_state` adds `updated_at`, `started_at` and `finished_at`, a status check constraint, a constraint that terminal states have `finished_at`, an index on `(tenant_id, status)`, and a trigger that rejects status changes outside the domain transition map. The trigger applies to direct SQL as well, so bypassing the repository cannot skip the state machine; it does not validate no-op writes that leave the status unchanged. Integration tests compare every distinct status pair with the domain map to prevent drift.
