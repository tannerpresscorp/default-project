import asyncio

import pytest
from pydantic import ValidationError

from apps.model_gateway.errors import ModelNotConfigured, ModelProviderError, ModelTimeout
from apps.model_gateway.gateway import ModelGateway
from apps.model_gateway.router import ModelRoute, ModelRouter
from packages.model_clients.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)
from packages.model_clients.fake import DeterministicModelProvider


def make_request(*contents: str) -> ModelRequest:
    return ModelRequest(
        messages=tuple(ModelMessage(role="user", content=content) for content in contents)
    )


def make_response(content: str = "ok") -> ModelResponse:
    return ModelResponse(content=content, usage=TokenUsage(input_tokens=1, output_tokens=1))


class RecordingProvider:
    name = "recording"

    def __init__(self, *, result=None, error: Exception | None = None, delay: float = 0.0) -> None:
        self.calls: list[tuple[str, ModelRequest]] = []
        self._result = result
        self._error = error
        self._delay = delay

    async def generate(self, model: str, request: ModelRequest):
        self.calls.append((model, request))
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return make_response() if self._result is None else self._result


def gateway_for(provider: RecordingProvider, *, timeout_seconds: float = 1.0) -> ModelGateway:
    router = ModelRouter({"chat": ModelRoute(provider, "upstream-chat")})
    return ModelGateway(router, timeout_seconds=timeout_seconds)


@pytest.mark.anyio
async def test_routes_logical_model_and_passes_the_provider_model():
    provider = RecordingProvider()
    gateway = gateway_for(provider)
    request = make_request("hello")

    response = await gateway.generate("chat", request)

    assert response == make_response()
    assert provider.calls == [("upstream-chat", request)]


@pytest.mark.anyio
async def test_unknown_logical_model_is_rejected_without_calling_a_provider():
    provider = RecordingProvider()
    gateway = gateway_for(provider)

    with pytest.raises(ModelNotConfigured) as error:
        await gateway.generate("missing", make_request("hello"))

    assert error.value.logical_model == "missing"
    assert provider.calls == []


@pytest.mark.anyio
async def test_timeout_is_normalized_and_reports_the_configured_limit():
    provider = RecordingProvider(delay=1.0)
    gateway = gateway_for(provider, timeout_seconds=0.01)

    with pytest.raises(ModelTimeout) as error:
        await gateway.generate("chat", make_request("hello"))

    assert error.value.timeout_seconds == 0.01
    assert len(provider.calls) == 1


@pytest.mark.anyio
async def test_provider_failure_is_normalized_without_leaking_details():
    provider = RecordingProvider(error=RuntimeError("prompt=secret-value"))
    gateway = gateway_for(provider)

    with pytest.raises(ModelProviderError) as error:
        await gateway.generate("chat", make_request("hello"))

    assert "secret-value" not in str(error.value)
    assert error.value.__suppress_context__ is True


@pytest.mark.anyio
async def test_non_response_provider_output_is_normalized():
    provider = RecordingProvider(result={"content": "not a ModelResponse"})
    gateway = gateway_for(provider)

    with pytest.raises(ModelProviderError):
        await gateway.generate("chat", make_request("hello"))


@pytest.mark.anyio
async def test_gateway_errors_from_a_provider_are_not_double_wrapped():
    provider = RecordingProvider(error=ModelNotConfigured("inner"))
    gateway = gateway_for(provider)

    with pytest.raises(ModelNotConfigured) as error:
        await gateway.generate("chat", make_request("hello"))

    assert error.value.logical_model == "inner"


@pytest.mark.anyio
async def test_deterministic_provider_is_repeatable_and_reports_usage():
    provider = DeterministicModelProvider()
    request = make_request("hello world")

    first = await provider.generate("small", request)
    second = await provider.generate("small", request)

    assert first == second
    assert first.content == "[small] hello world"
    assert first.usage == TokenUsage(input_tokens=2, output_tokens=3)


@pytest.mark.anyio
async def test_deterministic_provider_caps_output_length():
    provider = DeterministicModelProvider(max_output_chars=5)

    response = await provider.generate("small", make_request("hello"))

    assert response.content == "[smal"


def test_router_rejects_invalid_logical_and_provider_model_names():
    provider = DeterministicModelProvider()

    with pytest.raises(ValueError):
        ModelRouter({"Bad Name": ModelRoute(provider, "upstream")})
    with pytest.raises(ValueError):
        ModelRouter({"chat": ModelRoute(provider, "Bad Model")})


def test_gateway_rejects_out_of_range_timeouts():
    router = ModelRouter({})

    with pytest.raises(ValueError):
        ModelGateway(router, timeout_seconds=0)
    with pytest.raises(ValueError):
        ModelGateway(router, timeout_seconds=61)


def test_requests_require_bounded_messages():
    with pytest.raises(ValidationError):
        ModelRequest(messages=())
    with pytest.raises(ValidationError):
        ModelMessage(role="user", content="")
    with pytest.raises(ValidationError):
        ModelMessage(role="developer", content="hello")
    with pytest.raises(ValidationError):
        ModelMessage(role="user", content="hello", extra="field")


def test_request_total_content_is_bounded():
    message = ModelMessage(role="user", content="a" * 70_000)

    with pytest.raises(ValidationError):
        ModelRequest(messages=(message, message, message))


def test_responses_require_content_and_non_negative_usage():
    with pytest.raises(ValidationError):
        ModelResponse(content="", usage=TokenUsage(input_tokens=0, output_tokens=0))
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=-1, output_tokens=0)
