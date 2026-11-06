from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    """Provider-neutral description of a tool exposed through the gateway."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    description: str = Field(min_length=1, max_length=500)
    input_schema: dict[str, Any]
    requires_approval: bool = False
    timeout_seconds: float = Field(default=5.0, gt=0, le=30)


class ToolResult(BaseModel):
    """Result returned to the caller; tool output remains untrusted content."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    content: Any
