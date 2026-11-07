"""pgvector retrieval against the migrated test database."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from apps.retrieval.service import RetrievalService
from packages.model_clients.embeddings import DeterministicEmbeddingProvider
from packages.persistence.database import tenant_transaction
from packages.schemas.retrieval import (
    IngestRequest,
    RetrievalDocument,
    SearchRequest,
)


async def seed_tenant(engine, tenant_id):
    async with tenant_transaction(engine, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'retrieval')"), {"id": tenant_id}
        )


@pytest.mark.anyio
async def test_ingest_and_search_rank_the_matching_chunk_first(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    collection = f"docs-{uuid4().hex[:8]}"
    try:
        await seed_tenant(engine, tenant_id)
        service = RetrievalService(engine, DeterministicEmbeddingProvider())
        ids = await service.ingest(
            tenant_id,
            IngestRequest(
                documents=(
                    RetrievalDocument(
                        collection=collection,
                        source="handbook",
                        content="alpha beta gamma deployment handbook",
                    ),
                    RetrievalDocument(
                        collection=collection,
                        source="notes",
                        content="delta epsilon unrelated material",
                    ),
                )
            ),
        )
        assert len(ids) == 2

        matches = await service.search(
            tenant_id,
            SearchRequest(
                query="alpha beta gamma deployment handbook", collection=collection, limit=5
            ),
        )

        assert matches
        assert matches[0].source == "handbook"
        assert matches[0].content.startswith("alpha beta gamma")
        assert matches[0].score > 0.99
        assert len(matches) <= 5
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_search_is_tenant_scoped_even_with_a_known_collection(database_url):
    engine = create_async_engine(database_url)
    tenant_a, tenant_b = uuid4(), uuid4()
    collection = f"docs-{uuid4().hex[:8]}"
    try:
        await seed_tenant(engine, tenant_a)
        await seed_tenant(engine, tenant_b)
        service = RetrievalService(engine, DeterministicEmbeddingProvider())
        await service.ingest(
            tenant_a,
            IngestRequest(
                documents=(
                    RetrievalDocument(collection=collection, source="secret", content="tenant a"),
                )
            ),
        )

        assert (
            await service.search(tenant_b, SearchRequest(query="tenant a", collection=collection))
            == ()
        )

        async with tenant_transaction(engine, tenant_b) as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM retrieval_chunks "
                        "WHERE collection = :collection AND tenant_id = :tenant"
                    ),
                    {"collection": collection, "tenant": tenant_a},
                )
            ).scalar_one()
        assert count == 0
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_collection_filter_excludes_other_collections(database_url):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    suffix = uuid4().hex[:8]
    try:
        await seed_tenant(engine, tenant_id)
        service = RetrievalService(engine, DeterministicEmbeddingProvider())
        await service.ingest(
            tenant_id,
            IngestRequest(
                documents=(
                    RetrievalDocument(
                        collection=f"alpha-{suffix}", source="a", content="shared token"
                    ),
                    RetrievalDocument(
                        collection=f"beta-{suffix}", source="b", content="shared token"
                    ),
                )
            ),
        )

        matches = await service.search(
            tenant_id, SearchRequest(query="shared token", collection=f"beta-{suffix}")
        )

        assert [match.source for match in matches] == ["b"]
    finally:
        await engine.dispose()
