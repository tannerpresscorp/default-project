# Agent runtime

Not implemented in Phase 1. `AgentRun` stores a status and immutable agent-version reference, but has no transition validation, orchestration, API, execution, checkpointing, cancellation, budgets or approval support. Phase 2 should implement a tested explicit state machine and durable relational run state; Phase 4 should use deterministic Temporal workflows with external operations in activities. Interactive requests must not become the only copy of critical state.
