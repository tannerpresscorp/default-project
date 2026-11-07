"""Temporal workflows against a real local dev server.

These tests are skipped unless TEMPORAL_CLI_PATH points at the Temporal CLI.
The dev server is started per test so no shared external service is required.
"""

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from apps.model_gateway.gateway import ModelGateway
from apps.model_gateway.router import ModelRoute, ModelRouter
from apps.workflow_worker.activities import RunActivities, ToolApprovalActivities
from apps.workflow_worker.contracts import RunWorkflowInput, ToolApprovalRequest
from apps.workflow_worker.workflows import AgentRunWorkflow, ToolApprovalWorkflow
from packages.domain.runs import RunStatus
from packages.domain.tools import ApprovalStatus
from packages.model_clients.fake import DeterministicModelProvider
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import AgentRunRepository


@pytest.fixture
def temporal_cli_path() -> str:
    path = os.getenv("TEMPORAL_CLI_PATH")
    if not path or not Path(path).is_file():
        pytest.skip("Set TEMPORAL_CLI_PATH to a Temporal CLI executable")
    return path


async def start_environment(temporal_cli_path: str) -> WorkflowEnvironment:
    return await WorkflowEnvironment.start_local(
        dev_server_existing_path=temporal_cli_path,
        ui=False,
    )


async def seed_run(engine: AsyncEngine, tenant_id: UUID) -> UUID:
    agent_id, version_id = uuid4(), uuid4()
    async with tenant_transaction(engine, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name) VALUES (:id, 'temporal')"),
            {"id": tenant_id},
        )
        await conn.execute(
            text("INSERT INTO agents (id, tenant_id, name) VALUES (:id, :tenant, 'agent')"),
            {"id": agent_id, "tenant": tenant_id},
        )
        await conn.execute(
            text(
                "INSERT INTO agent_versions (id, tenant_id, agent_id, code, prompt, "
                "model_policy, tool_policy, retrieval_config) "
                "VALUES (:id, :tenant, :agent, 'sha', 'p', 'm', 't', 'r')"
            ),
            {"id": version_id, "tenant": tenant_id, "agent": agent_id},
        )
        run = await AgentRunRepository(conn, tenant_id).create(
            {"agent_id": agent_id, "agent_version_id": version_id}
        )
        return run["id"]


async def run_status(engine: AsyncEngine, tenant_id: UUID, run_id: UUID) -> str:
    async with tenant_transaction(engine, tenant_id) as conn:
        return (
            await conn.execute(text("SELECT status FROM agent_runs WHERE id = :id"), {"id": run_id})
        ).scalar_one()


def gateway_for_models(logical_models: tuple[str, ...]) -> ModelGateway:
    routes = {
        name: ModelRoute(DeterministicModelProvider(), f"offline-{name}") for name in logical_models
    }
    return ModelGateway(ModelRouter(routes), timeout_seconds=5.0)


@pytest.mark.anyio
async def test_run_workflow_completes_and_persists_state(database_url, temporal_cli_path):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    queue = f"runs-{uuid4()}"
    try:
        run_id = await seed_run(engine, tenant_id)
        activities = RunActivities(engine, gateway_for_models(("chat",)))
        async with await start_environment(temporal_cli_path) as env:
            async with Worker(
                env.client,
                task_queue=queue,
                workflows=[AgentRunWorkflow],
                activities=[
                    activities.start,
                    activities.generate,
                    activities.complete,
                    activities.fail,
                ],
            ):
                result = await env.client.execute_workflow(
                    AgentRunWorkflow.run,
                    RunWorkflowInput(
                        tenant_id=str(tenant_id),
                        run_id=str(run_id),
                        prompt="hello durable world",
                    ),
                    id=f"run-{uuid4()}",
                    task_queue=queue,
                )

        assert result.run_id == str(run_id)
        assert result.status == RunStatus.SUCCEEDED.value
        assert result.output.startswith("[offline-chat] hello durable world")
        assert result.input_tokens > 0
        assert result.output_tokens > 0
        assert await run_status(engine, tenant_id, run_id) == RunStatus.SUCCEEDED.value
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_run_workflow_marks_the_run_failed_when_generation_fails(
    database_url, temporal_cli_path
):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    queue = f"runs-{uuid4()}"
    try:
        run_id = await seed_run(engine, tenant_id)
        activities = RunActivities(engine, gateway_for_models(()))
        async with await start_environment(temporal_cli_path) as env:
            async with Worker(
                env.client,
                task_queue=queue,
                workflows=[AgentRunWorkflow],
                activities=[
                    activities.start,
                    activities.generate,
                    activities.complete,
                    activities.fail,
                ],
            ):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        AgentRunWorkflow.run,
                        RunWorkflowInput(
                            tenant_id=str(tenant_id),
                            run_id=str(run_id),
                            prompt="this model is not configured",
                            logical_model="missing",
                        ),
                        id=f"run-{uuid4()}",
                        task_queue=queue,
                    )

        assert await run_status(engine, tenant_id, run_id) == RunStatus.FAILED.value
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_approval_workflow_waits_for_signal_and_persists_decision(
    database_url, temporal_cli_path
):
    engine = create_async_engine(database_url)
    tenant_id = uuid4()
    queue = f"approvals-{uuid4()}"
    approval_id = uuid4()
    try:
        async with tenant_transaction(engine, tenant_id) as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, 'approvals')"),
                {"id": tenant_id},
            )
        activities = ToolApprovalActivities(engine)
        async with await start_environment(temporal_cli_path) as env:
            async with Worker(
                env.client,
                task_queue=queue,
                workflows=[ToolApprovalWorkflow],
                activities=[activities.request, activities.decide, activities.expire],
            ):
                handle = await env.client.start_workflow(
                    ToolApprovalWorkflow.run,
                    ToolApprovalRequest(
                        tenant_id=str(tenant_id),
                        approval_id=str(approval_id),
                        tool_name="delete_account",
                        arguments_digest="a" * 64,
                        requested_by="runner",
                        timeout_seconds=60,
                    ),
                    id=f"approval-{uuid4()}",
                    task_queue=queue,
                )
                await handle.signal(ToolApprovalWorkflow.decide, args=[True, "operator"])
                result = await handle.result()

        assert result.approval_id == str(approval_id)
        assert result.approved is True
        assert result.decided_by == "operator"
        async with tenant_transaction(engine, tenant_id) as conn:
            row = (
                (
                    await conn.execute(
                        text("SELECT status, decided_by FROM tool_approvals WHERE id = :id"),
                        {"id": approval_id},
                    )
                )
                .mappings()
                .one()
            )
        assert row["status"] == ApprovalStatus.APPROVED.value
        assert row["decided_by"] == "operator"
    finally:
        await engine.dispose()
