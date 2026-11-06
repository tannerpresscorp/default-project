"""Deterministic offline provider for tests, examples and local development only."""

from packages.model_clients.contracts import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)


class DeterministicModelProvider(ModelProvider):
    """Repeatable provider that performs no network access and keeps no state."""

    name = "deterministic"

    def __init__(self, *, max_output_chars: int = 2_000) -> None:
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be positive")
        self._max_output_chars = max_output_chars

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse:
        prompt = "\n".join(message.content for message in request.messages)
        content = f"[{model}] {prompt}"[: self._max_output_chars]
        return ModelResponse(
            content=content,
            usage=TokenUsage(
                input_tokens=sum(len(message.content.split()) for message in request.messages),
                output_tokens=len(content.split()),
            ),
        )
