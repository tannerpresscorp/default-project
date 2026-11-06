from collections.abc import Mapping
from typing import Protocol
from uuid import UUID


class ToolPolicy(Protocol):
    """Authorization boundary for tool discovery and invocation."""

    async def is_allowed(self, tenant_id: UUID, tool_name: str) -> bool: ...


class AllowlistToolPolicy:
    """Explicit tenant allowlists; every unlisted tenant/tool pair is denied."""

    def __init__(self, allowed: Mapping[UUID, frozenset[str]]) -> None:
        self._allowed = {tenant_id: frozenset(names) for tenant_id, names in allowed.items()}

    async def is_allowed(self, tenant_id: UUID, tool_name: str) -> bool:
        return tool_name in self._allowed.get(tenant_id, frozenset())
