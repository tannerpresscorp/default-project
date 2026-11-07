"""Provider-neutral embedding contracts and a deterministic offline embedder."""

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol

from packages.domain.retrieval import EMBEDDING_DIMENSIONS

MAX_BATCH_SIZE = 100
MAX_EMBEDDING_CHARS = 20_000

_TOKEN = re.compile(r"[a-z0-9]+")


class EmbeddingError(ValueError):
    """The embedding request or provider output is invalid."""


class EmbeddingProvider(Protocol):
    """Adapter boundary for embedding providers; no vendor SDK belongs here."""

    name: str
    dimensions: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class DeterministicEmbeddingProvider:
    """Repeatable, local embedding provider for tests and development only.

    Each token is hashed into one vector dimension and the result is L2
    normalized. Collisions are possible, so this is not a semantic model and
    must never be presented as production retrieval quality.
    """

    name = "deterministic"

    def __init__(self, *, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        if dimensions < 8 or dimensions > 16_000:
            raise ValueError("dimensions must be between 8 and 16000")
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if len(texts) > MAX_BATCH_SIZE:
            raise EmbeddingError("embedding batch is too large")
        vectors: list[list[float]] = []
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingError("embedding text must not be empty")
            if len(text) > MAX_EMBEDDING_CHARS:
                raise EmbeddingError("embedding text is too large")
            vectors.append(self._vectorize(text))
        return vectors

    def _vectorize(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        tokens = _TOKEN.findall(text.lower())
        for token in tokens or [text]:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            values[int.from_bytes(digest, "big") % self.dimensions] += 1.0
        magnitude = sum(value * value for value in values) ** 0.5
        if magnitude == 0:
            return values
        return [value / magnitude for value in values]
