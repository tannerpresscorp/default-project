# Retrieval

Phase 5 implements tenant-scoped pgvector retrieval through `apps/retrieval/service.py`, exposed by `POST /v1/retrieval/documents` and `POST /v1/retrieval/search`. See [docs/architecture/retrieval.md](../../docs/architecture/retrieval.md). Document parsing, chunking, reranking and retrieval-augmented generation are not implemented.
