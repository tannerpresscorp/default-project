# Platform architecture: Phase 1

The existing Django product catalog and React clients remain independent. `apps/api` is a new FastAPI control-plane foundation using its own configuration, dependencies, database and migrations. It currently exposes only liveness, readiness, generated OpenAPI, and an authenticated session endpoint; it does not implement agent CRUD or execution.

Shared Python packages own identity, domain types, schemas, observability, and PostgreSQL persistence. Placeholder directories are not deployable services. The tool gateway foundation is in process only and is not wired to the API or runtime. Later phases introduce logical runtime, model gateways, Temporal workers, retrieval, sandbox and evaluations; logical boundaries need not imply separate deployments.

PostgreSQL is authoritative for platform records; Redis is provisioned locally for later ephemeral use but is not yet connected to the platform. Production should use managed PostgreSQL and Redis, not the local Compose stack. Temporal, object storage, Kubernetes, usage pipelines and metrics are not implemented yet.

See [development](development.md), [security](security.md), [multi-tenancy](multi-tenancy.md), and the [ADRs](../adr/).
