import asyncio
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.tool_gateway.errors import (
    ToolApprovalRequired,
    ToolExecutionError,
    ToolNotAllowed,
    ToolNotFound,
    ToolTimeout,
    ToolValidationError,
)
from apps.tool_gateway.gateway import ToolGateway
from apps.tool_gateway.registry import InMemoryToolRegistry
from packages.policies.tools import AllowlistToolPolicy
from packages.schemas.tools import ToolDefinition

CITY_SCHEMA = {
    "type": "object",
    "properties": {"city": {"type": "string"}},
    "required": ["city"],
    "additionalProperties": False,
}
_MISSING = object()


def tool_definition(
    name: str,
    *,
    schema: dict[str, Any] | None = None,
    requires_approval: bool = False,
    timeout_seconds: float = 1.0,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} tool",
        input_schema=schema or CITY_SCHEMA,
        requires_approval=requires_approval,
        timeout_seconds=timeout_seconds,
    )


class FakeTool:
    def __init__(
        self,
        definition: ToolDefinition,
        *,
        result: Any = _MISSING,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.definition = definition
        self.calls: list[dict[str, Any]] = []
        self._result = result
        self._error = error
        self._delay = delay

    async def invoke(self, arguments: dict[str, Any]) -> Any:
        self.calls.append(dict(arguments))
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return arguments if self._result is _MISSING else self._result


def gateway_for(
    tools: list[FakeTool], allowed: dict[Any, frozenset[str]]
) -> tuple[ToolGateway, InMemoryToolRegistry]:
    registry = InMemoryToolRegistry(tools)
    return ToolGateway(registry, AllowlistToolPolicy(allowed)), registry


@pytest.mark.anyio
async def test_discovery_returns_only_tools_allowed_for_the_tenant():
    alpha, beta = FakeTool(tool_definition("alpha")), FakeTool(tool_definition("beta"))
    tenant_a, tenant_b = uuid4(), uuid4()
    gateway, _ = gateway_for(
        [beta, alpha],
        {
            tenant_a: frozenset({"alpha", "beta"}),
            tenant_b: frozenset({"beta", "missing"}),
        },
    )

    assert [item.name for item in await gateway.discover(tenant_a)] == ["alpha", "beta"]
    assert [item.name for item in await gateway.discover(tenant_b)] == ["beta"]
    assert await gateway.discover(uuid4()) == ()


@pytest.mark.anyio
async def test_invoke_returns_the_tool_result_and_passes_arguments():
    tool = FakeTool(tool_definition("weather"), result={"forecast": "sunny"})
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"weather"})})

    result = await gateway.invoke(tenant, "weather", {"city": "Paris"})

    assert result.tool_name == "weather"
    assert result.content == {"forecast": "sunny"}
    assert tool.calls == [{"city": "Paris"}]


@pytest.mark.anyio
async def test_invoke_denies_unlisted_and_unknown_tools_without_revealing_the_registry():
    tool = FakeTool(tool_definition("weather"))
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"other"})})

    with pytest.raises(ToolNotAllowed):
        await gateway.invoke(tenant, "weather", {"city": "Paris"})
    with pytest.raises(ToolNotAllowed):
        await gateway.invoke(tenant, "unregistered", {})

    assert tool.calls == []


@pytest.mark.anyio
async def test_invoke_reports_an_allowed_but_unregistered_tool_as_not_found():
    tenant = uuid4()
    gateway, _ = gateway_for([], {tenant: frozenset({"missing"})})

    with pytest.raises(ToolNotFound):
        await gateway.invoke(tenant, "missing", {})


@pytest.mark.anyio
async def test_invoke_rejects_invalid_arguments_without_executing_or_leaking_values():
    tool = FakeTool(tool_definition("weather"))
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"weather"})})

    with pytest.raises(ToolValidationError) as error:
        await gateway.invoke(tenant, "weather", {"city": 123})

    assert error.value.path == ("city",)
    assert "123" not in str(error.value)
    assert tool.calls == []


@pytest.mark.anyio
async def test_invoke_denies_remote_schema_references_without_network_access(monkeypatch):
    schema = {
        "type": "object",
        "properties": {"city": {"$ref": "https://example.invalid/city.json"}},
        "required": ["city"],
    }
    tool = FakeTool(tool_definition("remote_ref", schema=schema))
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"remote_ref"})})

    network_calls = []

    def fail_network(*args, **kwargs):
        network_calls.append(args)
        raise RuntimeError("network access is forbidden")

    monkeypatch.setattr("urllib.request.urlopen", fail_network)

    with pytest.raises(ToolValidationError):
        await gateway.invoke(tenant, "remote_ref", {"city": "Paris"})
    assert network_calls == []
    assert tool.calls == []


@pytest.mark.anyio
async def test_invoke_denies_tools_that_require_approval():
    tool = FakeTool(tool_definition("delete_account", requires_approval=True))
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"delete_account"})})

    with pytest.raises(ToolApprovalRequired):
        await gateway.invoke(tenant, "delete_account", {"city": "Paris"})

    assert tool.calls == []


@pytest.mark.anyio
async def test_invoke_times_out_and_reports_the_configured_limit():
    tool = FakeTool(tool_definition("slow", timeout_seconds=0.01), delay=1.0)
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"slow"})})

    with pytest.raises(ToolTimeout) as error:
        await gateway.invoke(tenant, "slow", {"city": "Paris"})

    assert error.value.timeout_seconds == 0.01
    assert len(tool.calls) == 1


@pytest.mark.anyio
async def test_invoke_wraps_unexpected_tool_failures_without_leaking_details():
    tool = FakeTool(tool_definition("broken"), error=RuntimeError("password=hunter2"))
    tenant = uuid4()
    gateway, _ = gateway_for([tool], {tenant: frozenset({"broken"})})

    with pytest.raises(ToolExecutionError) as error:
        await gateway.invoke(tenant, "broken", {"city": "Paris"})

    assert "hunter2" not in str(error.value)
    assert error.value.__suppress_context__ is True


def test_registry_rejects_duplicate_names_and_invalid_schemas():
    registry = InMemoryToolRegistry([FakeTool(tool_definition("alpha"))])

    with pytest.raises(ValueError):
        registry.register(FakeTool(tool_definition("alpha")))
    with pytest.raises(ValueError):
        InMemoryToolRegistry([FakeTool(tool_definition("array", schema={"type": "array"}))])
    with pytest.raises(ValueError):
        InMemoryToolRegistry(
            [
                FakeTool(
                    tool_definition("broken", schema={"type": "object", "properties": "not-a-dict"})
                )
            ]
        )


def test_tool_definition_rejects_unsafe_names_and_excessive_timeouts():
    with pytest.raises(ValidationError):
        ToolDefinition(name="Bad Name", description="bad", input_schema={"type": "object"})
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="slow",
            description="slow",
            input_schema={"type": "object"},
            timeout_seconds=31,
        )


@pytest.mark.anyio
async def test_allowlist_policy_is_default_deny():
    tenant = uuid4()
    policy = AllowlistToolPolicy({tenant: frozenset({"allowed"})})

    assert await policy.is_allowed(tenant, "allowed") is True
    assert await policy.is_allowed(tenant, "denied") is False
    assert await policy.is_allowed(uuid4(), "allowed") is False
