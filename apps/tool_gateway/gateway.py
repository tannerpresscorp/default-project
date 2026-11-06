import asyncio
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from referencing import Registry

from packages.policies.tools import ToolPolicy
from packages.schemas.tools import ToolDefinition, ToolResult

from .errors import (
    ToolApprovalRequired,
    ToolExecutionError,
    ToolGatewayError,
    ToolNotAllowed,
    ToolNotFound,
    ToolTimeout,
    ToolValidationError,
)
from .registry import ToolRegistry


class ToolGateway:
    """Discover and invoke registered tools under tenant policy and schema validation."""

    def __init__(self, registry: ToolRegistry, policy: ToolPolicy) -> None:
        self._registry = registry
        self._policy = policy

    async def discover(self, tenant_id: UUID) -> tuple[ToolDefinition, ...]:
        allowed: list[ToolDefinition] = []
        for definition in self._registry.definitions():
            if await self._policy.is_allowed(tenant_id, definition.name):
                allowed.append(definition)
        return tuple(allowed)

    async def invoke(
        self, tenant_id: UUID, tool_name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        # Authorize before lookup so unauthorized callers cannot enumerate the registry.
        if not await self._policy.is_allowed(tenant_id, tool_name):
            raise ToolNotAllowed(tool_name)
        tool = self._registry.get(tool_name)
        if tool is None:
            raise ToolNotFound(tool_name)
        definition = tool.definition
        if definition.requires_approval:
            raise ToolApprovalRequired(tool_name)
        self._validate(definition, arguments)
        try:
            async with asyncio.timeout(definition.timeout_seconds):
                content = await tool.invoke(arguments)
        except TimeoutError as error:
            raise ToolTimeout(tool_name, definition.timeout_seconds) from error
        except ToolGatewayError:
            raise
        except Exception:
            raise ToolExecutionError(tool_name) from None
        return ToolResult(tool_name=tool_name, content=content)

    @staticmethod
    def _validate(definition: ToolDefinition, arguments: dict[str, Any]) -> None:
        # An empty registry disables jsonschema's default remote $ref retrieval.
        validator = Draft202012Validator(definition.input_schema, registry=Registry())
        try:
            error = next(validator.iter_errors(arguments), None)
        except Exception:
            raise ToolValidationError(definition.name, ()) from None
        if error is None:
            return
        raise ToolValidationError(definition.name, tuple(error.absolute_path)) from None
