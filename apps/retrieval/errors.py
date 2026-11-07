"""Retrieval application boundary."""


class RetrievalError(RuntimeError):
    """Base class for retrieval failures that are safe to expose to callers."""


class RetrievalDimensionError(RetrievalError):
    """The embedder and stored vector dimensions do not match."""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"embedding dimension {actual} does not match expected {expected}")
