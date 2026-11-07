import math

import pytest
from pydantic import ValidationError

from apps.retrieval.errors import RetrievalDimensionError
from apps.retrieval.service import RetrievalService
from packages.domain.retrieval import EMBEDDING_DIMENSIONS
from packages.model_clients.embeddings import (
    MAX_BATCH_SIZE,
    DeterministicEmbeddingProvider,
    EmbeddingError,
)
from packages.schemas.retrieval import (
    IngestRequest,
    RetrievalDocument,
    SearchRequest,
)


@pytest.mark.anyio
async def test_deterministic_embeddings_repeat_and_are_unit_length():
    provider = DeterministicEmbeddingProvider()

    first = (await provider.embed(["Alpha beta gamma"]))[0]
    second = (await provider.embed(["Alpha beta gamma"]))[0]

    assert first == second
    assert len(first) == EMBEDDING_DIMENSIONS
    assert math.isclose(sum(value * value for value in first), 1.0, rel_tol=1e-9)


@pytest.mark.anyio
async def test_embeddings_differ_for_different_content():
    provider = DeterministicEmbeddingProvider()

    first, second = await provider.embed(["alpha", "beta"])

    assert first != second


@pytest.mark.anyio
async def test_embedding_provider_rejects_empty_oversized_and_large_batches():
    provider = DeterministicEmbeddingProvider()

    with pytest.raises(EmbeddingError):
        await provider.embed([""])
    with pytest.raises(EmbeddingError):
        await provider.embed(["x" * 20_001])
    with pytest.raises(EmbeddingError):
        await provider.embed(["text"] * (MAX_BATCH_SIZE + 1))


def test_retrieval_contracts_are_bounded_and_forbid_extra_fields():
    with pytest.raises(ValidationError):
        SearchRequest(query="x", limit=0)
    with pytest.raises(ValidationError):
        SearchRequest(query="x", limit=51)
    with pytest.raises(ValidationError):
        SearchRequest(query="")
    with pytest.raises(ValidationError):
        SearchRequest(query="x", collection="Bad Collection")
    with pytest.raises(ValidationError):
        RetrievalDocument(collection="docs", source="s", content="")
    with pytest.raises(ValidationError):
        RetrievalDocument(collection="docs", source="s", content="c", extra="field")
    with pytest.raises(ValidationError):
        IngestRequest(documents=())


def test_service_rejects_an_embedder_with_the_wrong_dimensions():
    with pytest.raises(RetrievalDimensionError):
        RetrievalService(object(), DeterministicEmbeddingProvider(dimensions=64))
