"""Temporal worker entry point for durable agent runs and approvals."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine
from temporalio.client import Client
from temporalio.worker import Worker

from apps.model_gateway.gateway import ModelGateway
from apps.model_gateway.router import ModelRoute, ModelRouter
from packages.config.settings import Settings
from packages.model_clients.fake import DeterministicModelProvider
from packages.observability.logging import configure_logging

from .activities import RunActivities, ToolApprovalActivities
from .workflows import AgentRunWorkflow, ToolApprovalWorkflow

TASK_QUEUE = "agent-runs"
logger = logging.getLogger(__name__)


def build_model_gateway() -> ModelGateway:
    """The only wired provider is the deterministic offline adapter."""
    router = ModelRouter({"chat": ModelRoute(DeterministicModelProvider(), "offline-chat")})
    return ModelGateway(router, timeout_seconds=10.0)


async def run_worker(settings: Settings) -> None:
    if not settings.database_url:
        raise RuntimeError("PLATFORM_DATABASE_URL is required to run the worker")
    if not settings.temporal_address:
        raise RuntimeError("PLATFORM_TEMPORAL_ADDRESS is required to run the worker")

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    activities = RunActivities(engine, build_model_gateway())
    approvals = ToolApprovalActivities(engine)
    try:
        client = await Client.connect(
            settings.temporal_address, namespace=settings.temporal_namespace
        )
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue or TASK_QUEUE,
            workflows=[AgentRunWorkflow, ToolApprovalWorkflow],
            activities=[
                activities.start,
                activities.generate,
                activities.complete,
                activities.fail,
                approvals.request,
                approvals.decide,
                approvals.expire,
            ],
        )
        logger.info(
            "workflow worker started",
            extra={"task_queue": settings.temporal_task_queue or TASK_QUEUE},
        )
        await worker.run()
    finally:
        await engine.dispose()


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run_worker(Settings()))
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("workflow worker stopped unexpectedly")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
