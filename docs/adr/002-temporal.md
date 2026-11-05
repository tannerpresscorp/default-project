# ADR-002: Temporal for durable workflows

## Context
Long-running runs must survive process restarts and wait for human decisions.
## Decision
Adopt Temporal in Phase 4; workflow code must remain deterministic and external calls belong in activities.
## Alternatives considered
In-process tasks cannot provide equivalent durability; custom queues require building orchestration semantics.
## Consequences
Workers, workflow history, retries and operational procedures must be managed; no Temporal integration exists yet.
## Operational risks
Stuck workflows, history growth, worker compatibility and duplicate side effects require monitoring and idempotency.
