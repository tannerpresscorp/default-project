import pytest
from pydantic import ValidationError

from packages.domain.usage import (
    DEFAULT_PRICE_BOOK,
    ModelPrice,
    PriceBook,
    UnknownModelPrice,
)
from packages.schemas.usage import UsageRequest


def test_price_computation_is_integer_and_rounds_up():
    price = ModelPrice(input_micros_per_million=2_000_000, output_micros_per_million=4_000_000)

    assert price.cost_micros(1_000, 500) == 4_000
    assert price.cost_micros(1, 0) == 2
    assert price.cost_micros(0, 0) == 0
    assert ModelPrice(0, 0).cost_micros(10_000_000, 10_000_000) == 0


def test_prices_reject_negative_values():
    with pytest.raises(ValueError):
        ModelPrice(-1, 0)
    with pytest.raises(ValueError):
        ModelPrice(0, -1)
    with pytest.raises(ValueError):
        ModelPrice(0, 0).cost_micros(-1, 0)


def test_unknown_models_fail_closed():
    with pytest.raises(UnknownModelPrice):
        PriceBook({"chat": ModelPrice(0, 0)}).price("missing")
    with pytest.raises(UnknownModelPrice):
        DEFAULT_PRICE_BOOK.price("vendor-model")


def test_default_price_book_does_not_claim_vendor_costs():
    assert DEFAULT_PRICE_BOOK.price("chat").cost_micros(1_000_000, 1_000_000) == 0
    assert DEFAULT_PRICE_BOOK.price("embedding").cost_micros(1_000_000, 0) == 0


def test_usage_requests_are_bounded_and_forbid_extra_fields():
    with pytest.raises(ValidationError):
        UsageRequest(logical_model="chat", input_tokens=-1, output_tokens=0)
    with pytest.raises(ValidationError):
        UsageRequest(logical_model="chat", input_tokens=0, output_tokens=-1)
    with pytest.raises(ValidationError):
        UsageRequest(logical_model="Chat", input_tokens=0, output_tokens=0)
    with pytest.raises(ValidationError):
        UsageRequest(logical_model="chat", input_tokens=0, output_tokens=0, cost_micros=1)
    with pytest.raises(ValidationError):
        UsageRequest(logical_model="chat", input_tokens=10_000_001, output_tokens=0)
