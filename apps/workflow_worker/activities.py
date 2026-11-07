"""Side-effecting activities. All database access stays tenant-scoped."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity
from temporalio.exceptions import ApplicationError

from apps.model_gateway.errors import ModelGatewayError, ModelNotConfigured
from apps.model_gateway.gateway import ModelGateway
from packages.domain.runs import RunStatus, is_terminal
from packages.domain.tools import ApprovalStatus
from packages.model_clients.contracts import ModelMessage, ModelRequest
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import (
    AgentRunRepository,
    AgentRunStateConflict,
    ToolApprovalRepository,
    ToolApprovalStateConflict,
)

from .contracts import (
    GenerationResult,
    RunCompletionInput,
    RunFailureInput,
    RunWorkflowInput,
    RunWorkflowResult,
    ToolApprovalDecision,
    ToolApprovalRequest,
)


def _run_ids(request: RunWorkflowInput | RunCompletionInput | RunFailureInput) -> tuple[UUID, UUID]:
    try:
        return UUID(request.tenant_id), UUID(request.run_id)
    except ValueError as exc:
        raise ApplicationError("run identity is invalid", non_retryable=True) from exc


def _approval_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApplicationError("approval identity is invalid", non_retryable=True) from exc


class RunActivities:
    """Model generation and run-state transitions; no vendor calls are made."""

    def __init__(self, engine: AsyncEngine, model_gateway: ModelGateway) -> None:
        self._engine = engine
        self._model_gateway = model_gateway

    @activity.defn(name="agent_run.start")
    async def start(self, request: RunWorkflowInput) -> str:
        tenant_id, run_id = _run_ids(request)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            repo = AgentRunRepository(conn, tenant_id)
            row = await repo.get(run_id)
            if row is None:
                raise ApplicationError("agent run not found", non_retryable=True)
            status = RunStatus(row["status"])
            if status is RunStatus.PENDING:
                try:
                    row = await repo.transition(
                        run_id, expected=RunStatus.PENDING, target=RunStatus.RUNNING
                    )
                except AgentRunStateConflict:
                    row = await repo.get(run_id)
            if row is None or RunStatus(row["status"]) is not RunStatus.RUNNING:
                raise ApplicationError("agent run is not runnable", non_retryable=True)
            return row["status"]

    @activity.defn(name="agent_run.generate")
    async def generate(self, request: RunWorkflowInput) -> GenerationResult:
        try:
            model_request = ModelRequest(
                messages=(ModelMessage(role="user", content=request.prompt),)
            )
        except ValueError as exc:
            raise ApplicationError("prompt is invalid", non_retryable=True) from exc
        try:
            response = await self._model_gateway.generate(request.logical_model, model_request)
        except ModelNotConfigured as exc:
            raise ApplicationError("model is not configured", non_retryable=True) from exc
        except ModelGatewayError as exc:
            raise ApplicationError("model generation failed") from exc
        return GenerationResult(
            content=response.content,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    @activity.defn(name="agent_run.complete")
    async def complete(self, request: RunCompletionInput) -> RunWorkflowResult:
        tenant_id, run_id = _run_ids(request)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            repo = AgentRunRepository(conn, tenant_id)
            row = await repo.get(run_id)
            if row is None:
                raise ApplicationError("agent run not found", non_retryable=True)
            status = RunStatus(row["status"])
            if status is not RunStatus.SUCCEEDED:
                if status is not RunStatus.RUNNING:
                    raise ApplicationError("agent run is not running", non_retryable=True)
                try:
                    row = await repo.transition(
                        run_id, expected=RunStatus.RUNNING, target=RunStatus.SUCCEEDED
                    )
                except AgentRunStateConflict:
                    row = await repo.get(run_id)
                    if row is None or RunStatus(row["status"]) is not RunStatus.SUCCEEDED:
                        raise ApplicationError(
                            "agent run changed concurrently", non_retryable=True
                        ) from None
            return RunWorkflowResult(
                run_id=request.run_id,
                status=row["status"],
                output=request.output,
                input_tokens=request.input_tokens,
                output_tokens=request.output_tokens,
            )

    @activity.defn(name="agent_run.fail")
    async def fail(self, request: RunFailureInput) -> None:
        tenant_id, run_id = _run_ids(request)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            repo = AgentRunRepository(conn, tenant_id)
            row = await repo.get(run_id)
            if row is None:
                return
            status = RunStatus(row["status"])
            if is_terminal(status):
                return
            try:
                await repo.transition(run_id, expected=status, target=RunStatus.FAILED)
            except AgentRunStateConflict:
                return


class ToolApprovalActivities:
    """Durable approval record lifecycle with idempotent activity retries."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @activity.defn(name="tool_approval.request")
    async def request(self, request: ToolApprovalRequest) -> None:
        tenant_id = _approval_id(request.tenant_id)
        approval_id = _approval_id(request.approval_id)
        expires_at = datetime.now(UTC) + timedelta(seconds=request.timeout_seconds)
        try:
            async with tenant_transaction(self._engine, tenant_id) as conn:
                repo = ToolApprovalRepository(conn, tenant_id)
                if await repo.get(approval_id) is not None:
                    return
                await repo.request(
                    approval_id=approval_id,
                    tool_name=request.tool_name,
                    arguments_digest=request.arguments_digest,
                    requested_by=request.requested_by,
                    expires_at=expires_at,
                )
        except IntegrityError:
            # A concurrent retry created the same deterministic approval first.
            return

    @activity.defn(name="tool_approval.decide")
    async def decide(self, request: ToolApprovalDecision) -> None:
        tenant_id = _approval_id(request.tenant_id)
        approval_id = _approval_id(request.approval_id)
        target = ApprovalStatus.APPROVED if request.approved else ApprovalStatus.DENIED
        async with tenant_transaction(self._engine, tenant_id) as conn:
            repo = ToolApprovalRepository(conn, tenant_id)
            try:
                await repo.decide(approval_id, status=target, decided_by=request.decided_by)
                return
            except ToolApprovalStateConflict:
                row = await repo.get(approval_id)
                if row is not None and row["status"] == target.value:
                    return
                raise ApplicationError(
                    "approval was already decided differently", non_retryable=True
                ) from None

    @activity.defn(name="tool_approval.expire")
    async def expire(self, request: ToolApprovalRequest) -> None:
        tenant_id = _approval_id(request.tenant_id)
        approval_id = _approval_id(request.approval_id)
        async with tenant_transaction(self._engine, tenant_id) as conn:
            repo = ToolApprovalRepository(conn, tenant_id)
            try:
                await repo.expire(approval_id)
            except ToolApprovalStateConflict:
                return
