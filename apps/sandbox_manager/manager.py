"""Governed sandbox facade with authorization, timeouts and bounded output."""

import asyncio
from uuid import UUID

from packages.schemas.sandbox import SandboxRequest, SandboxResult

from .backend import SandboxBackend
from .errors import (
    SandboxDenied,
    SandboxError,
    SandboxExecutionError,
    SandboxTimeout,
)
from .policy import SandboxPolicy

MAX_OUTPUT_BYTES = 64 * 1024


class SandboxManager:
    """Authorize, time-limit and normalize an isolated execution attempt."""

    def __init__(
        self,
        backend: SandboxBackend,
        policy: SandboxPolicy,
        *,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
    ) -> None:
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        self._backend = backend
        self._policy = policy
        self._max_output_bytes = max_output_bytes

    async def execute(self, tenant_id: UUID, request: SandboxRequest) -> SandboxResult:
        if not await self._policy.is_enabled(tenant_id):
            raise SandboxDenied(tenant_id)
        try:
            async with asyncio.timeout(request.timeout_seconds):
                result = await self._backend.execute(request)
        except SandboxError:
            raise
        except TimeoutError as error:
            raise SandboxTimeout(request.timeout_seconds) from error
        except Exception:
            raise SandboxExecutionError() from None
        return self._bounded(result)

    def _bounded(self, result: SandboxResult) -> SandboxResult:
        stdout, stdout_cut = self._truncate(result.stdout)
        stderr, stderr_cut = self._truncate(result.stderr)
        if not stdout_cut and not stderr_cut and not result.truncated:
            return result
        return SandboxResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=result.exit_code,
            truncated=True,
        )

    def _truncate(self, value: str) -> tuple[str, bool]:
        encoded = value.encode("utf-8", errors="replace")
        if len(encoded) <= self._max_output_bytes:
            return value, False
        return encoded[: self._max_output_bytes].decode("utf-8", errors="ignore"), True
