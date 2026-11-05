# ADR-006: OpenTelemetry observability

## Context
Agent runs span HTTP, workflows, tools, models and data stores.
## Decision
Use OpenTelemetry for traces and Prometheus-compatible metrics; Phase 1 establishes HTTP trace hooks only.
## Alternatives considered
Vendor-specific instrumentation impedes portability; uncorrelated logs are insufficient.
## Consequences
Use bounded metric labels and protect sensitive data; deployment must provide an exporter and collector.
## Operational risks
High-cardinality labels, sensitive telemetry, sampling and collector failure can increase cost or expose data.
