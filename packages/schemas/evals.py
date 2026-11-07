"""Provider-independent evaluation contracts."""

from pydantic import BaseModel, ConfigDict, Field


class EvalCase(BaseModel):
    """One deterministic check: expected text must appear in the output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    prompt: str = Field(min_length=1, max_length=10_000)
    expected_substring: str = Field(min_length=1, max_length=10_000)


class EvalCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    passed: bool
    output: str | None = None
    error: str | None = None


class EvalReport(BaseModel):
    """Deterministic pass/fail summary. Output text remains untrusted data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    results: tuple[EvalCaseResult, ...]
    passed: int = Field(ge=0)
    total: int = Field(ge=0)
