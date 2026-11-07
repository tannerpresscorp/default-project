"""Bounded budget contracts. Limits are optional; absent means unlimited."""

from pydantic import BaseModel, ConfigDict, Field

MAX_COST_MICROS = 10**15
MAX_TOKENS = 10**12


class BudgetLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    monthly_cost_micros: int | None = Field(default=None, ge=0, le=MAX_COST_MICROS)
    monthly_tokens: int | None = Field(default=None, ge=0, le=MAX_TOKENS)


class BudgetStatus(BaseModel):
    """Limits plus usage in the current UTC month."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    monthly_cost_micros: int | None
    monthly_tokens: int | None
    events: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
