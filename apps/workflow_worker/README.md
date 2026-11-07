# Workflow worker

Phase 4 implements a Temporal worker with deterministic workflows and tenant-scoped activities.

- `contracts.py`: frozen dataclasses crossing the workflow boundary.
- `workflows.py`: `AgentRunWorkflow` and `ToolApprovalWorkflow`. This module imports no database, HTTP or model-client code.
- `activities.py`: `agent_run.start`, `agent_run.generate`, `agent_run.complete`, `agent_run.fail`, `agent_run.cancel`, and the `tool_approval.*` activities. Every database operation runs inside `tenant_transaction`. Successful completion records usage idempotently.
- `worker.py`: configuration and process entry point.

Run it with:

```sh
PLATFORM_DATABASE_URL=postgresql+asyncpg://platform_app:local_app_only@127.0.0.1:55432/platform \
PLATFORM_TEMPORAL_ADDRESS=127.0.0.1:7233 \
.venv-platform/bin/python -m apps.workflow_worker.worker
```

The only wired model provider is the deterministic offline adapter. No vendor calls or production Temporal deployment exists. Workflow cancellation persists `CANCELLED`; the API exposes it under `/v1/runs/{id}/cancel`. Budget enforcement lives in `packages/usage` and is applied at API submission, not inside the worker.
