"""Tenant-scoped pgvector retrieval."""

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.ext.asyncio import AsyncEngine

from apps.retrieval.errors import RetrievalDimensionError
from packages.domain.retrieval import EMBEDDING_DIMENSIONS
from packages.model_clients.embeddings import EmbeddingProvider
from packages.persistence.database import tenant_transaction
from packages.persistence.models import RetrievalChunk
from packages.schemas.retrieval import IngestRequest, RetrievalMatch, SearchRequest


class RetrievalService:
    """Embed and search chunks inside the caller's tenant transaction."""

    def __init__(self, engine: AsyncEngine, embedder: EmbeddingProvider) -> None:
        if embedder.dimensions != EMBEDDING_DIMENSIONS:
            raise RetrievalDimensionError(EMBEDDING_DIMENSIONS, embedder.dimensions)
        self._engine = engine
        self._embedder = embedder

    async def ingest(self, tenant_id: UUID, request: IngestRequest) -> tuple[UUID, ...]:
        vectors = await self._embedder.embed([document.content for document in request.documents])
        self._check_dimensions(vectors)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            rows = (
                await conn.execute(
                    cast(Table, RetrievalChunk.__table__)
                    .insert()
                    .values(
                        [
                            {
                                "tenant_id": tenant_id,
                                "collection": document.collection,
                                "source": document.source,
                                "content": document.content,
                                "embedding": vector,
                            }
                            for document, vector in zip(request.documents, vectors, strict=True)
                        ]
                    )
                    .returning(RetrievalChunk.__table__.c.id)
                )
            ).scalars()
            return tuple(rows.all())

    async def search(self, tenant_id: UUID, request: SearchRequest) -> tuple[RetrievalMatch, ...]:
        vectors = await self._embedder.embed([request.query])
        self._check_dimensions(vectors)
        distance = RetrievalChunk.__table__.c.embedding.cosine_distance(vectors[0])
        stmt = (
            select(
                RetrievalChunk.__table__.c.id,
                RetrievalChunk.__table__.c.collection,
                RetrievalChunk.__table__.c.source,
                RetrievalChunk.__table__.c.content,
                (1 - distance).label("score"),
            )
            .where(RetrievalChunk.__table__.c.tenant_id == tenant_id)
            .order_by(distance)
            .limit(request.limit)
        )
        if request.collection is not None:
            stmt = stmt.where(RetrievalChunk.__table__.c.collection == request.collection)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            rows = (await conn.execute(stmt)).mappings().all()
        return tuple(
            RetrievalMatch(
                id=row["id"],
                collection=row["collection"],
                source=row["source"],
                content=row["content"],
                score=float(row["score"]),
            )
            for row in rows
        )

    def _check_dimensions(self, vectors: Sequence[Sequence[float]]) -> None:
        if any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
            raise RetrievalDimensionError(EMBEDDING_DIMENSIONS, len(vectors[0]) if vectors else 0)
