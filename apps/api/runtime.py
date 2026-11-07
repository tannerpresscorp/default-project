"""Authenticated run submission, status, cancellation, budgets and retrieval.

The HTTP layer owns no state. PostgreSQL remains authoritative; Temporal runs
are dispatched through an injectable protocol so the API can be tested without
a workflow server. Streaming is server-sent events backed by bounded polling,
not a second source of truth.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode

from apps.workflow_worker.contracts import RunWorkflowInput
from apps.workflow_worker.workflows import AgentRunWorkflow
from packages.auth.context import authenticated_principal
from packages.auth.identity import Principal
from packages.domain.runs import RunStatus, is_terminal
from packages.observability.metrics import Metrics
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import (
    AgentRunRepository,
    AgentRunStateConflict,
)
from packages.schemas.budgets import BudgetLimits, BudgetStatus
from packages.schemas.retrieval import (
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
)
from packages.schemas.runs import RunCreateRequest, RunList, RunView
from packages.usage.budget import BudgetExceeded

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runtime"])
PrincipalDep = Annotated[Principal, Depends(authenticated_principal)]
STREAM_SECONDS = 300
STREAM_INTERVAL_SECONDS = 1.0


class RunDispatcher(Protocol):
    """Minimal boundary around the workflow service."""

    async def start(
        self, *, tenant_id: UUID, run_id: UUID, prompt: str, logical_model: str
    ) -> None: ...

    async def cancel(self, *, tenant_id: UUID, run_id: UUID) -> None: ...


class RetrievalApi(Protocol):
    async def ingest(self, tenant_id: UUID, request: IngestRequest) -> tuple[UUID, ...]: ...

    async def search(self, tenant_id: UUID, request: SearchRequest) -> tuple[Any, ...]: ...


class BudgetApi(Protocol):
    async def check(self, tenant_id: UUID) -> None: ...

    async def status(self, tenant_id: UUID) -> BudgetStatus: ...

    async def set_limits(self, tenant_id: UUID, limits: BudgetLimits) -> BudgetStatus: ...


def workflow_id(tenant_id: UUID, run_id: UUID) -> str:
    return f"agent-run-{tenant_id}-{run_id}"


class TemporalRunDispatcher:
    """Start and cancel workflows on a connected Temporal client."""

    def __init__(self, client: Client, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start(
        self, *, tenant_id: UUID, run_id: UUID, prompt: str, logical_model: str
    ) -> None:
        await self._client.start_workflow(
            AgentRunWorkflow.run,
            RunWorkflowInput(
                tenant_id=str(tenant_id),
                run_id=str(run_id),
                prompt=prompt,
                logical_model=logical_model,
            ),
            id=workflow_id(tenant_id, run_id),
            task_queue=self._task_queue,
        )

    async def cancel(self, *, tenant_id: UUID, run_id: UUID) -> None:
        handle = self._client.get_workflow_handle(workflow_id(tenant_id, run_id))
        try:
            await handle.cancel()
        except RPCError as exc:
            if exc.status != RPCStatusCode.NOT_FOUND:
                raise


def _engine(request: Request) -> AsyncEngine:
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    return engine


def _dispatcher(request: Request) -> RunDispatcher:
    dispatcher = request.app.state.run_dispatcher
    if dispatcher is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Run dispatch unavailable")
    return dispatcher


def _retrieval(request: Request) -> RetrievalApi:
    service = request.app.state.retrieval
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Retrieval unavailable")
    return service


def _budget(request: Request) -> BudgetApi:
    service = request.app.state.budget
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Budgets unavailable")
    return service


def _metrics(request: Request) -> Metrics:
    return request.app.state.metrics


def run_view(row: RowMapping) -> RunView:
    return RunView(
        id=row["id"],
        agent_id=row["agent_id"],
        agent_version_id=row["agent_version_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


async def _load_run(engine: AsyncEngine, tenant_id: UUID, run_id: UUID) -> RowMapping | None:
    async with tenant_transaction(engine, tenant_id) as conn:
        return await AgentRunRepository(conn, tenant_id).get(run_id)


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.post(
    "/runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunView,
    summary="Submit an agent run",
)
async def create_run(
    payload: RunCreateRequest,
    request: Request,
    principal: PrincipalDep,
) -> RunView:
    engine = _engine(request)
    dispatcher = _dispatcher(request)
    try:
        await _budget(request).check(principal.tenant_id)
    except BudgetExceeded:
        _metrics(request).increment("platform_budget_rejections_total")
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Tenant budget exhausted",
            headers={"Retry-After": "3600"},
        ) from None
    try:
        async with tenant_transaction(engine, principal.tenant_id) as conn:
            row = await AgentRunRepository(conn, principal.tenant_id).create(
                {
                    "agent_id": payload.agent_id,
                    "agent_version_id": payload.agent_version_id,
                }
            )
    except IntegrityError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Agent version not found"
        ) from None
    try:
        await dispatcher.start(
            tenant_id=principal.tenant_id,
            run_id=row["id"],
            prompt=payload.prompt,
            logical_model=payload.logical_model,
        )
    except Exception:
        logger.exception("failed to dispatch agent run", extra={"run_id": str(row["id"])})
        try:
            async with tenant_transaction(engine, principal.tenant_id) as conn:
                await AgentRunRepository(conn, principal.tenant_id).transition(
                    row["id"], expected=RunStatus.PENDING, target=RunStatus.FAILED
                )
        except (AgentRunStateConflict, LookupError):
            pass
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Run dispatch unavailable"
        ) from None
    _metrics(request).increment("platform_runs_submitted_total")
    return run_view(row)


@router.get("/runs/{run_id}", response_model=RunView, summary="Read one agent run")
async def get_run(run_id: UUID, request: Request, principal: PrincipalDep) -> RunView:
    row = await _load_run(_engine(request), principal.tenant_id, run_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run_view(row)


@router.get("/runs", response_model=RunList, summary="List agent runs")
async def list_runs(
    request: Request,
    principal: PrincipalDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunList:
    async with tenant_transaction(_engine(request), principal.tenant_id) as conn:
        rows = await AgentRunRepository(conn, principal.tenant_id).list(limit=limit, offset=offset)
    return RunList(runs=tuple(run_view(row) for row in rows))


@router.post("/runs/{run_id}/cancel", response_model=RunView, summary="Cancel an agent run")
async def cancel_run(run_id: UUID, request: Request, principal: PrincipalDep) -> RunView:
    engine = _engine(request)
    async with tenant_transaction(engine, principal.tenant_id) as conn:
        repo = AgentRunRepository(conn, principal.tenant_id)
        row = await repo.get(run_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
        if is_terminal(RunStatus(row["status"])):
            raise HTTPException(status.HTTP_409_CONFLICT, "Run already finished")
        try:
            row = await repo.transition(
                run_id,
                expected=RunStatus(row["status"]),
                target=RunStatus.CANCELLED,
            )
        except AgentRunStateConflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "Run already finished") from None
    dispatcher = request.app.state.run_dispatcher
    if dispatcher is not None:
        try:
            await dispatcher.cancel(tenant_id=principal.tenant_id, run_id=run_id)
        except Exception:
            # PostgreSQL already records the terminal state; a missing or
            # unreachable workflow must not roll that back.
            logger.exception("failed to cancel workflow", extra={"run_id": str(run_id)})
    _metrics(request).increment("platform_run_cancellations_total")
    return run_view(row)


@router.get("/runs/{run_id}/events", summary="Stream run status events")
async def run_events(run_id: UUID, request: Request, principal: PrincipalDep) -> StreamingResponse:
    engine = _engine(request)

    async def events() -> AsyncIterator[str]:
        last: str | None = None
        deadline = time.monotonic() + STREAM_SECONDS
        while True:
            if await request.is_disconnected():
                return
            row = await _load_run(engine, principal.tenant_id, run_id)
            if row is None:
                yield _sse("error", '{"code":"not_found"}')
                return
            current = str(row["status"])
            if current != last:
                last = current
                yield _sse("status", run_view(row).model_dump_json())
            if is_terminal(RunStatus(current)):
                yield _sse("end", "{}")
                return
            if time.monotonic() >= deadline:
                yield _sse("end", '{"reason":"timeout"}')
                return
            await asyncio.sleep(STREAM_INTERVAL_SECONDS)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/budget", response_model=BudgetStatus, summary="Read tenant budget status")
async def get_budget(request: Request, principal: PrincipalDep) -> BudgetStatus:
    return await _budget(request).status(principal.tenant_id)


@router.put("/budget", response_model=BudgetStatus, summary="Replace tenant budget limits")
async def put_budget(
    limits: BudgetLimits,
    request: Request,
    principal: PrincipalDep,
) -> BudgetStatus:
    return await _budget(request).set_limits(principal.tenant_id, limits)


@router.post(
    "/retrieval/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=IngestResponse,
    summary="Ingest retrieval chunks",
)
async def ingest_documents(
    payload: IngestRequest,
    request: Request,
    principal: PrincipalDep,
) -> IngestResponse:
    ids = await _retrieval(request).ingest(principal.tenant_id, payload)
    _metrics(request).increment("platform_retrieval_ingestions_total")
    return IngestResponse(ids=tuple(ids))


@router.post(
    "/retrieval/search",
    response_model=SearchResponse,
    summary="Search retrieval chunks",
)
async def search_documents(
    payload: SearchRequest,
    request: Request,
    principal: PrincipalDep,
) -> SearchResponse:
    matches = await _retrieval(request).search(principal.tenant_id, payload)
    _metrics(request).increment("platform_retrieval_searches_total")
    return SearchResponse(matches=tuple(matches))
