"""Tenant authorization for sandbox execution; every unlisted tenant is denied."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID


class SandboxPolicy(Protocol):
    async def is_enabled(self, tenant_id: UUID) -> bool: ...


class DenyAllSandboxPolicy:
    """Default policy: no tenant may execute code."""

    async def is_enabled(self, tenant_id: UUID) -> bool:
        return False


class AllowlistSandboxPolicy:
    """Explicit per-tenant enablement; absence means denial."""

    def __init__(self, enabled: Iterable[UUID]) -> None:
        self._enabled = frozenset(enabled)

    async def is_enabled(self, tenant_id: UUID) -> bool:
        return tenant_id in self._enabled
