"""Bounded contracts for submitting and observing agent runs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_PROMPT_CHARS = 100_000
LOGICAL_MODEL_PATTERN = r"^[a-z][a-z0-9_.-]{0,63}$"


class RunCreateRequest(BaseModel):
    """A caller cannot choose the tenant, run ID, status or timestamps."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agent_id: UUID
    agent_version_id: UUID
    prompt: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    logical_model: str = Field(default="chat", pattern=LOGICAL_MODEL_PATTERN)


class RunView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    agent_id: UUID
    agent_version_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunList(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    runs: tuple[RunView, ...]
