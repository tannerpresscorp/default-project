import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.sandbox_manager.backend import DisabledSandboxBackend
from apps.sandbox_manager.errors import (
    SandboxDenied,
    SandboxExecutionError,
    SandboxTimeout,
    SandboxUnavailable,
)
from apps.sandbox_manager.manager import SandboxManager
from apps.sandbox_manager.policy import AllowlistSandboxPolicy, DenyAllSandboxPolicy
from packages.schemas.sandbox import SandboxRequest, SandboxResult


class EchoBackend:
    def __init__(self, result: SandboxResult | None = None) -> None:
        self.requests: list[SandboxRequest] = []
        self._result = result or SandboxResult(stdout="ok", exit_code=0)

    async def execute(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        return self._result


class FailingBackend:
    async def execute(self, request: SandboxRequest) -> SandboxResult:
        raise RuntimeError("secret=leaked")


class SlowBackend:
    async def execute(self, request: SandboxRequest) -> SandboxResult:
        await asyncio.sleep(1)
        return SandboxResult()


def test_requests_are_bounded_and_reject_extra_fields():
    with pytest.raises(ValidationError):
        SandboxRequest(code="")
    with pytest.raises(ValidationError):
        SandboxRequest(code="x" * 100_001)
    with pytest.raises(ValidationError):
        SandboxRequest(code="print()", timeout_seconds=0)
    with pytest.raises(ValidationError):
        SandboxRequest(code="print()", timeout_seconds=61)
    with pytest.raises(ValidationError):
        SandboxRequest(code="print()", memory_mb=32)
    with pytest.raises(ValidationError):
        SandboxRequest(code="print()", language="bash")
    with pytest.raises(ValidationError):
        SandboxRequest(code="print()", network=True)


@pytest.mark.anyio
async def test_default_policy_denies_before_the_backend_is_called():
    backend = EchoBackend()
    manager = SandboxManager(backend, DenyAllSandboxPolicy())

    with pytest.raises(SandboxDenied):
        await manager.execute(uuid4(), SandboxRequest(code="print('hello')"))

    assert backend.requests == []


@pytest.mark.anyio
async def test_allowlisted_tenant_still_denied_without_a_real_backend():
    tenant_id = uuid4()
    manager = SandboxManager(DisabledSandboxBackend(), AllowlistSandboxPolicy([tenant_id]))

    with pytest.raises(SandboxUnavailable):
        await manager.execute(tenant_id, SandboxRequest(code="print('hello')"))


@pytest.mark.anyio
async def test_allowlisted_tenant_reaches_an_explicit_backend():
    tenant_id = uuid4()
    backend = EchoBackend()
    manager = SandboxManager(backend, AllowlistSandboxPolicy([tenant_id]))
    request = SandboxRequest(code="print('hello')")

    result = await manager.execute(tenant_id, request)

    assert result.stdout == "ok"
    assert backend.requests == [request]


@pytest.mark.anyio
async def test_unexpected_backend_errors_are_normalized():
    tenant_id = uuid4()
    manager = SandboxManager(FailingBackend(), AllowlistSandboxPolicy([tenant_id]))

    with pytest.raises(SandboxExecutionError) as error:
        await manager.execute(tenant_id, SandboxRequest(code="print('hello')"))

    assert "secret" not in str(error.value)


@pytest.mark.anyio
async def test_timeouts_are_enforced_by_the_manager():
    tenant_id = uuid4()
    manager = SandboxManager(SlowBackend(), AllowlistSandboxPolicy([tenant_id]))

    with pytest.raises(SandboxTimeout):
        await manager.execute(
            tenant_id, SandboxRequest(code="print('hello')", timeout_seconds=0.01)
        )


@pytest.mark.anyio
async def test_output_is_truncated_to_the_configured_limit():
    tenant_id = uuid4()
    backend = EchoBackend(SandboxResult(stdout="a" * 10, stderr="b" * 10))
    manager = SandboxManager(backend, AllowlistSandboxPolicy([tenant_id]), max_output_bytes=4)

    result = await manager.execute(tenant_id, SandboxRequest(code="print('hello')"))

    assert result.stdout == "aaaa"
    assert result.stderr == "bbbb"
    assert result.truncated is True
