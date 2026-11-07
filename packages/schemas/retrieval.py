"""Bounded retrieval contracts. Content remains untrusted data."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

COLLECTION_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"


class RetrievalDocument(BaseModel):
    """One caller-supplied document chunk to embed and store."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    collection: str = Field(pattern=COLLECTION_PATTERN)
    source: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=20_000)


class IngestRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    documents: tuple[RetrievalDocument, ...] = Field(min_length=1, max_length=100)


class SearchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    collection: str | None = Field(default=None, pattern=COLLECTION_PATTERN)
    limit: int = Field(default=5, ge=1, le=50)


class RetrievalMatch(BaseModel):
    """A ranked chunk. The score is cosine similarity in [-1, 1]."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    collection: str
    source: str
    content: str
    score: float = Field(ge=-1.0, le=1.0)
