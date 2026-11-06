# Agent runtime

Phase 2 implements the durable run state machine only: agent-run statuses, allowed transitions, lifecycle timestamps, and tenant-scoped optimistic transitions. It does not implement orchestration, an API, execution, checkpointing, cancellation, budgets, approvals, or Temporal. Phase 4 should use deterministic Temporal workflows with external operations in activities. Interactive requests must not become the only copy of critical state.

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
