# ADR-005: pgvector as initial vector backend

## Context
Retrieval needs similarity search and tenant-aware filtering.
## Decision
Start with pgvector behind a replaceable retrieval interface in Phase 5.
## Alternatives considered
A dedicated vector service adds infrastructure and migration burden before its scale is justified.
## Consequences
Keep provenance and tenant/collection filters explicit. Migration `0003_retrieval` creates the `vector` extension, a tenant-scoped `retrieval_chunks` table with forced RLS, and an HNSW cosine index. The deterministic offline embedder is development-only; production embedding quality, ingestion pipelines and load testing remain later work.
## Operational risks
Index performance, recall, tenant leakage and database resource contention require evaluation and load testing.
