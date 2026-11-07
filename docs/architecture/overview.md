# Platform architecture

The existing Django product catalog and React clients remain independent. `apps/api` is an additive FastAPI control-plane foundation using its own configuration, dependencies, PostgreSQL database and migrations. It exposes liveness, readiness, generated OpenAPI, an authenticated session endpoint, and an authenticated runtime surface for agent runs, budgets and retrieval.

Shared Python packages own identity, domain types, schemas, observability and PostgreSQL persistence. The implemented platform pieces are:

- **Model gateway** (`apps/model_gateway`): static logical routing, bounded requests, one timeout, normalized errors and a deterministic offline provider. No vendor calls.
- **Tool gateway** (`apps/tool_gateway`): tenant allowlists, JSON Schema validation, audited idempotent invocations, durable approvals and timeouts. No MCP or network tools.
- **Workflow worker** (`apps/workflow_worker`): deterministic Temporal workflows for agent runs and human approvals; all database and model effects are activities. Cancellation persists `CANCELLED`, and successful runs record usage idempotently.
- **Runtime API** (`apps/api/runtime.py`): submit/read/list/cancel runs, bounded SSE status events, monthly budget read/replace, and retrieval ingest/search. Temporal dispatch is optional and fails closed without `PLATFORM_TEMPORAL_ADDRESS`. Public `/metrics` exposes bounded in-process Prometheus counters.
- **Retrieval** (`apps/retrieval`): tenant-scoped pgvector chunk storage and cosine search with an HNSW index. The deterministic embedder is development-only.
- **Sandbox boundary** (`apps/sandbox_manager`): deny-by-default authorization, timeout, output bounding and a backend protocol. No real code execution.
- **Usage and budgets** (`packages/usage`): an append-only token ledger with idempotent recording and optional tenant monthly admission limits. No reservations or invoicing.
- **Evaluations** (`apps/eval_service`): a deterministic runner and fixed offline smoke dataset. No vendor or semantic grading.

PostgreSQL is authoritative for platform records; Redis is provisioned locally for later ephemeral use but is not connected to the platform. Production should use managed PostgreSQL and Redis, not the local Compose stack. Temporal is used for durable workflow state, but production clustering and managed deployment remain out of scope. The Helm chart under `infra/helm/agent-platform/` is gated, linted and rendered in CI, and never applied by CI.

See [development](development.md), [security](security.md), [multi-tenancy](multi-tenancy.md), and the [ADRs](../adr/).
