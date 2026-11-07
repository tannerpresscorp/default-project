"""Sandbox failures that are safe to expose. Messages never include code or output."""


class SandboxError(Exception):
    """Base class for denied or failed sandbox execution."""


class SandboxDenied(SandboxError):
    """The tenant is not allowed to execute code."""

    def __init__(self, tenant_id: object) -> None:
        self.tenant_id = tenant_id
        super().__init__("sandbox execution is not allowed for this tenant")


class SandboxUnavailable(SandboxError):
    """No isolated execution backend is configured."""

    def __init__(self) -> None:
        super().__init__("sandbox execution is not available")


class SandboxTimeout(SandboxError):
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(f"sandbox execution timed out after {timeout_seconds} seconds")


class SandboxExecutionError(SandboxError):
    """An unexpected backend failure, normalized to avoid leaking details."""

    def __init__(self) -> None:
        super().__init__("sandbox execution failed")
