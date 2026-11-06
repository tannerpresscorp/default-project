"""Provider-neutral contracts for model access."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_MESSAGES = 200
MAX_MESSAGE_CHARS = 100_000
MAX_REQUEST_CHARS = 200_000


class ModelMessage(BaseModel):
    """One provider-neutral message in a model request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ModelRequest(BaseModel):
    """Bounded conversation input; prompt size limits apply before any provider call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    messages: tuple[ModelMessage, ...] = Field(min_length=1, max_length=MAX_MESSAGES)

    @model_validator(mode="after")
    def content_within_limit(self) -> "ModelRequest":
        total = sum(len(message.content) for message in self.messages)
        if total > MAX_REQUEST_CHARS:
            raise ValueError("request content exceeds the limit")
        return self


class TokenUsage(BaseModel):
    """Provider-reported usage. Accounting and persistence are not implemented."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ModelResponse(BaseModel):
    """Provider-neutral completion; content remains untrusted model output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str = Field(min_length=1)
    usage: TokenUsage
    finish_reason: Literal["stop", "length"] = "stop"


class ModelProvider(Protocol):
    """Adapter boundary; vendor SDKs and network calls belong only in implementations."""

    name: str

    async def generate(self, model: str, request: ModelRequest) -> ModelResponse: ...
