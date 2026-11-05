# ADR-005: pgvector as initial vector backend

## Context
Retrieval needs similarity search and tenant-aware filtering.
## Decision
Start with pgvector behind a replaceable retrieval interface in Phase 5.
## Alternatives considered
A dedicated vector service adds infrastructure and migration burden before its scale is justified.
## Consequences
Keep provenance and tenant/collection filters explicit; the extension and retrieval are not installed by the migration yet.
## Operational risks
Index performance, recall, tenant leakage and database resource contention require evaluation and load testing.
