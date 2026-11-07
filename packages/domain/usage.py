"""Deterministic pricing and usage domain types.

Prices are integer micro-units (1 USD = 1,000,000) per million tokens so
accounting never depends on floating-point arithmetic. The default book prices
the offline provider at zero; it does not claim any real vendor cost.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

MICROS_PER_UNIT: Final[int] = 1_000_000
TOKENS_PER_PRICE_UNIT: Final[int] = 1_000_000


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Price in micro-units per one million input/output tokens."""

    input_micros_per_million: int
    output_micros_per_million: int

    def __post_init__(self) -> None:
        if self.input_micros_per_million < 0 or self.output_micros_per_million < 0:
            raise ValueError("model prices must not be negative")

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must not be negative")
        micros = (
            input_tokens * self.input_micros_per_million
            + output_tokens * self.output_micros_per_million
        )
        # Round up so a positive price never becomes free through truncation.
        return (micros + TOKENS_PER_PRICE_UNIT - 1) // TOKENS_PER_PRICE_UNIT


class UnknownModelPrice(KeyError):
    """No price is configured for the logical model."""

    def __init__(self, logical_model: str) -> None:
        self.logical_model = logical_model
        super().__init__(f"no price configured for model {logical_model}")


class PriceBook:
    """Explicit logical-model pricing; unknown models fail closed."""

    def __init__(self, prices: Mapping[str, ModelPrice]) -> None:
        self._prices = MappingProxyType(dict(prices))

    def price(self, logical_model: str) -> ModelPrice:
        try:
            return self._prices[logical_model]
        except KeyError:
            raise UnknownModelPrice(logical_model) from None


DEFAULT_PRICE_BOOK: Final[PriceBook] = PriceBook(
    {
        "chat": ModelPrice(0, 0),
        "embedding": ModelPrice(0, 0),
    }
)
