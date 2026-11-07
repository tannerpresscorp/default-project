# ADR-002: Temporal for durable workflows

## Context
Long-running runs must survive process restarts and wait for human decisions.
## Decision
Adopt Temporal in Phase 4; workflow code must remain deterministic and external calls belong in activities.
## Alternatives considered
In-process tasks cannot provide equivalent durability; custom queues require building orchestration semantics.
## Consequences
Workers, workflow history, retries and operational procedures must be managed. Phase 4 implements `AgentRunWorkflow` and `ToolApprovalWorkflow` with a Temporal worker; workflow code is deterministic and all database/model effects run in activities. Production clustering, retention, archival and worker deployment are still later-phase work.
## Operational risks
Stuck workflows, history growth, worker compatibility and duplicate side effects require monitoring and idempotency.
