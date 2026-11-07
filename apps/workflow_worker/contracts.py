"""Serializable contracts crossing the Temporal workflow boundary."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunWorkflowInput:
    tenant_id: str
    run_id: str
    prompt: str
    logical_model: str = "chat"


@dataclass(frozen=True)
class RunWorkflowResult:
    run_id: str
    status: str
    output: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class GenerationResult:
    content: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class RunCompletionInput:
    tenant_id: str
    run_id: str
    output: str
    input_tokens: int
    output_tokens: int
    logical_model: str = "chat"


@dataclass(frozen=True)
class RunCancelInput:
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class RunFailureInput:
    tenant_id: str
    run_id: str


@dataclass(frozen=True)
class ToolApprovalRequest:
    tenant_id: str
    approval_id: str
    tool_name: str
    arguments_digest: str
    requested_by: str
    timeout_seconds: int = 86_400


@dataclass(frozen=True)
class ToolApprovalDecision:
    tenant_id: str
    approval_id: str
    approved: bool
    decided_by: str


@dataclass(frozen=True)
class ToolApprovalResult:
    approval_id: str
    approved: bool
    decided_by: str | None
