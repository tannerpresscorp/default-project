"""Bounded sandbox contracts. Code and output are untrusted content."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SandboxRequest(BaseModel):
    """One isolated execution request. Only languages with an adapter are accepted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: Literal["python"] = "python"
    code: str = Field(min_length=1, max_length=100_000)
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    memory_mb: int = Field(default=256, ge=64, le=2048)


class SandboxResult(BaseModel):
    """Captured output. The caller must treat it as data, never as instructions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    truncated: bool = False
