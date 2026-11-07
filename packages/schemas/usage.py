"""Bounded usage accounting contracts. Costs are computed server-side."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_TOKENS_PER_EVENT = 10_000_000


class UsageRequest(BaseModel):
    """Token usage reported by a governed model call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID | None = None
    logical_model: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    input_tokens: int = Field(ge=0, le=MAX_TOKENS_PER_EVENT)
    output_tokens: int = Field(ge=0, le=MAX_TOKENS_PER_EVENT)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class UsageRecorded(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    logical_model: str
    input_tokens: int
    output_tokens: int
    cost_micros: int


class UsageTotals(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    events: int
    input_tokens: int
    output_tokens: int
    cost_micros: int
