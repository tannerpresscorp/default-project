import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from apps.workflow_worker.contracts import (
    RunWorkflowInput,
    ToolApprovalRequest,
    ToolApprovalResult,
)
from packages.config.settings import Settings


def test_temporal_settings_have_safe_defaults():
    settings = Settings()

    assert settings.temporal_address is None
    assert settings.temporal_namespace == "default"
    assert settings.temporal_task_queue == "agent-runs"


def test_temporal_settings_are_configurable_from_the_platform_prefix(monkeypatch):
    monkeypatch.setenv("PLATFORM_TEMPORAL_ADDRESS", "temporal.example:7233")
    monkeypatch.setenv("PLATFORM_TEMPORAL_NAMESPACE", "agents")
    monkeypatch.setenv("PLATFORM_TEMPORAL_TASK_QUEUE", "runs")

    settings = Settings()

    assert settings.temporal_address == "temporal.example:7233"
    assert settings.temporal_namespace == "agents"
    assert settings.temporal_task_queue == "runs"


def test_workflow_contracts_are_frozen_and_bounded():
    request = RunWorkflowInput(tenant_id="tenant", run_id="run", prompt="hello")
    assert request.logical_model == "chat"
    with pytest.raises(FrozenInstanceError):
        request.prompt = "changed"  # type: ignore[misc]

    approval = ToolApprovalRequest(
        tenant_id="tenant",
        approval_id="approval",
        tool_name="delete_account",
        arguments_digest="a" * 64,
        requested_by="runner",
    )
    assert approval.timeout_seconds == 86_400

    result = ToolApprovalResult(approval_id="approval", approved=False, decided_by=None)
    assert result.decided_by is None


def test_workflows_do_not_import_io_libraries():
    source = (
        Path(__file__).resolve().parents[2] / "apps" / "workflow_worker" / "workflows.py"
    ).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)

    forbidden = {
        "sqlalchemy",
        "asyncpg",
        "httpx",
        "packages.persistence",
        "packages.model_clients",
        "apps.model_gateway",
    }
    assert not {
        name
        for name in imported
        if any(name == bad or name.startswith(f"{bad}.") for bad in forbidden)
    }
