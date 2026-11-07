# Platform architecture

The existing Django product catalog and React clients remain independent. `apps/api` is an additive FastAPI control-plane foundation using its own configuration, dependencies, PostgreSQL database and migrations. It exposes liveness, readiness, generated OpenAPI, and an authenticated session endpoint; it does not yet expose agent CRUD or a run-submission API.

Shared Python packages own identity, domain types, schemas, observability and PostgreSQL persistence. The implemented platform pieces are:

- **Model gateway** (`apps/model_gateway`): static logical routing, bounded requests, one timeout, normalized errors and a deterministic offline provider. No vendor calls.
- **Tool gateway** (`apps/tool_gateway`): tenant allowlists, JSON Schema validation, audited idempotent invocations, durable approvals and timeouts. No MCP or network tools.
- **Workflow worker** (`apps/workflow_worker`): deterministic Temporal workflows for agent runs and human approvals; all database and model effects are activities.
- **Retrieval** (`apps/retrieval`): tenant-scoped pgvector chunk storage and cosine search with an HNSW index. The deterministic embedder is development-only.
- **Sandbox boundary** (`apps/sandbox_manager`): deny-by-default authorization, timeout, output bounding and a backend protocol. No real code execution.
- **Usage ledger** (`packages/usage`): append-only token accounting with integer micro-unit pricing. No budget enforcement.
- **Evaluations** (`apps/eval_service`): a deterministic runner and fixed offline smoke dataset. No vendor or semantic grading.

PostgreSQL is authoritative for platform records; Redis is provisioned locally for later ephemeral use but is not connected to the platform. Production should use managed PostgreSQL and Redis, not the local Compose stack. Temporal is used for durable workflow state, but production clustering, object storage, Kubernetes deployment and metrics are not implemented. The manifests under `infra/k8s/` are gated, unvalidated starting points and are never applied by CI.

See [development](development.md), [security](security.md), [multi-tenancy](multi-tenancy.md), and the [ADRs](../adr/).
