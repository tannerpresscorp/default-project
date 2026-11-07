"""Durable workflow definitions. Only deterministic code belongs here.

External effects run in activities registered by the worker; this module must
not import SQLAlchemy, model clients or other I/O libraries.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from .contracts import (
    GenerationResult,
    RunCompletionInput,
    RunFailureInput,
    RunWorkflowInput,
    RunWorkflowResult,
    ToolApprovalDecision,
    ToolApprovalRequest,
    ToolApprovalResult,
)

ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
)
ACTIVITY_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class AgentRunWorkflow:
    """Durable start -> generate -> complete sequence with failure compensation."""

    @workflow.run
    async def run(self, request: RunWorkflowInput) -> RunWorkflowResult:
        if not 0 < len(request.prompt) <= 100_000:
            raise ApplicationError("prompt is invalid", non_retryable=True)
        await workflow.execute_activity(
            "agent_run.start",
            request,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )
        try:
            generated = await workflow.execute_activity(
                "agent_run.generate",
                request,
                result_type=GenerationResult,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=ACTIVITY_RETRY,
            )
            completed = await workflow.execute_activity(
                "agent_run.complete",
                RunCompletionInput(
                    tenant_id=request.tenant_id,
                    run_id=request.run_id,
                    output=generated.content,
                    input_tokens=generated.input_tokens,
                    output_tokens=generated.output_tokens,
                ),
                result_type=RunWorkflowResult,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=ACTIVITY_RETRY,
            )
            return RunWorkflowResult(
                run_id=completed.run_id,
                status=completed.status,
                output=completed.output,
                input_tokens=completed.input_tokens,
                output_tokens=completed.output_tokens,
            )
        except Exception:
            await workflow.execute_activity(
                "agent_run.fail",
                RunFailureInput(tenant_id=request.tenant_id, run_id=request.run_id),
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=ACTIVITY_RETRY,
            )
            raise


@workflow.defn
class ToolApprovalWorkflow:
    """Wait durably for one human approval decision, then persist it."""

    def __init__(self) -> None:
        self._decision: tuple[bool, str] | None = None

    @workflow.signal
    def decide(self, approved: bool, decided_by: str) -> None:
        if self._decision is None:
            self._decision = (approved, decided_by)

    @workflow.run
    async def run(self, request: ToolApprovalRequest) -> ToolApprovalResult:
        if not 0 < request.timeout_seconds <= 604_800:
            raise ApplicationError("approval timeout is invalid", non_retryable=True)
        await workflow.execute_activity(
            "tool_approval.request",
            request,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(seconds=request.timeout_seconds),
            )
        except TimeoutError:
            await workflow.execute_activity(
                "tool_approval.expire",
                request,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=ACTIVITY_RETRY,
            )
            raise ApplicationError("approval timed out", non_retryable=True) from None

        assert self._decision is not None
        approved, decided_by = self._decision
        await workflow.execute_activity(
            "tool_approval.decide",
            ToolApprovalDecision(
                tenant_id=request.tenant_id,
                approval_id=request.approval_id,
                approved=approved,
                decided_by=decided_by,
            ),
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )
        return ToolApprovalResult(
            approval_id=request.approval_id,
            approved=approved,
            decided_by=decided_by,
        )
