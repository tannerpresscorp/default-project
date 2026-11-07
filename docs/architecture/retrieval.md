# Retrieval

Phase 5 implements tenant-scoped pgvector retrieval. It stores embedded chunks and returns ranked content, but does not provide ingestion APIs, document parsing, chunking, reranking, hybrid search or retrieval-augmented generation wiring.

## Components

- `packages/model_clients/embeddings.py` defines the `EmbeddingProvider` protocol and a deterministic offline provider. The offline provider hashes tokens into vector dimensions and L2-normalizes the result. It is repeatable and useful for tests, but it is not a semantic model and must not be presented as production retrieval quality.
- `packages/schemas/retrieval.py` bounds documents, batches and searches. Content is capped at 20,000 characters, batches at 100 documents and searches at 50 results.
- `packages/persistence/models.py` defines `RetrievalChunk` with a 1536-dimension vector, a `(tenant_id, collection)` index and an HNSW `vector_cosine_ops` index.
- `apps/retrieval/service.py` embeds and writes inside `tenant_transaction`, and filters search by tenant before applying the optional collection filter.

## Isolation

`retrieval_chunks` has forced PostgreSQL RLS with separate read and write checks. `RetrievalService` never accepts a tenant from the request payload; the caller supplies the verified tenant UUID. A tenant cannot see another tenant's rows even when it knows the collection name, and the integration tests cover that case.

## Operations

Migration `0003_retrieval` runs `CREATE EXTENSION IF NOT EXISTS vector`. The migration role must be allowed to create the extension (CI uses a superuser; a supervised DBA provisions it once on restricted installations). Similarity search uses cosine distance, with `score = 1 - distance`.
