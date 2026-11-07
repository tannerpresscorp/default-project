"""Sandbox backend boundary. A backend is the only component allowed to execute code."""

from typing import Protocol

from packages.schemas.sandbox import SandboxRequest, SandboxResult

from .errors import SandboxUnavailable


class SandboxBackend(Protocol):
    """Isolated execution adapter; implementations must enforce their own isolation."""

    async def execute(self, request: SandboxRequest) -> SandboxResult: ...


class DisabledSandboxBackend:
    """Deny-by-default backend used until a hardened adapter is deployed."""

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        raise SandboxUnavailable()
