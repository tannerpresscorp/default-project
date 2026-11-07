"""Audited, idempotent tool invocation with durable approval checks."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from packages.domain.tools import ApprovalStatus, InvocationStatus
from packages.persistence.database import tenant_transaction
from packages.persistence.repository import (
    ToolApprovalRepository,
    ToolInvocationRepository,
    ToolInvocationStateConflict,
)
from packages.schemas.tools import ToolResult

from .errors import (
    ToolApprovalRequired,
    ToolGatewayError,
    ToolInvocationConflict,
    ToolInvocationError,
    ToolInvocationInFlight,
    ToolInvocationResultUnavailable,
    ToolNotAllowed,
)
from .gateway import ToolGateway

MAX_AUDIT_RESULT_BYTES = 65_536


def arguments_digest(arguments: dict[str, Any]) -> str:
    """Hash canonical JSON so raw arguments never enter the audit table."""
    try:
        payload = json.dumps(
            arguments, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
        )
    except (TypeError, ValueError) as exc:
        raise ToolInvocationError("tool arguments must be finite JSON values") from exc
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ToolInvocationService:
    """Reserve an idempotency key, enforce approval, invoke, and record the outcome."""

    def __init__(self, engine: AsyncEngine, gateway: ToolGateway) -> None:
        self._engine = engine
        self._gateway = gateway

    async def invoke(
        self,
        tenant_id: UUID,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        approval_id: UUID | None = None,
    ) -> ToolResult:
        if idempotency_key is not None and not 0 < len(idempotency_key) <= 128:
            raise ToolInvocationError("idempotency key must be between 1 and 128 characters")
        digest = arguments_digest(arguments)

        if idempotency_key is not None:
            existing = await self._by_idempotency_key(tenant_id, idempotency_key)
            if existing is not None:
                return self._replay(existing, digest)

        try:
            async with tenant_transaction(self._engine, tenant_id) as conn:
                invocation = await ToolInvocationRepository(conn, tenant_id).start(
                    tool_name=tool_name,
                    arguments_digest=digest,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            # A concurrent caller won the unique idempotency reservation.
            if idempotency_key is None:
                raise
            existing = await self._by_idempotency_key(tenant_id, idempotency_key)
            if existing is None:
                raise ToolInvocationError("could not reserve the idempotency key") from None
            return self._replay(existing, digest)

        approved = await self._is_approved(tenant_id, tool_name, digest, approval_id)
        try:
            result = await self._gateway.invoke(
                tenant_id,
                tool_name,
                arguments,
                approval_granted=approved,
            )
        except ToolGatewayError as error:
            denied = isinstance(error, (ToolNotAllowed, ToolApprovalRequired))
            await self._finish(
                tenant_id,
                invocation["id"],
                InvocationStatus.DENIED if denied else InvocationStatus.FAILED,
                error_code=type(error).__name__,
            )
            raise

        await self._finish(
            tenant_id,
            invocation["id"],
            InvocationStatus.SUCCEEDED,
            result=self._audit_result(result.content),
        )
        return result

    async def _by_idempotency_key(self, tenant_id: UUID, key: str) -> Any | None:
        async with tenant_transaction(self._engine, tenant_id) as conn:
            return await ToolInvocationRepository(conn, tenant_id).by_idempotency_key(key)

    def _replay(self, row: Any, digest: str) -> ToolResult:
        if row["arguments_digest"] != digest:
            raise ToolInvocationError(
                "the idempotency key was already used with different arguments"
            )
        status = InvocationStatus(row["status"])
        if status is InvocationStatus.STARTED:
            raise ToolInvocationInFlight(row["idempotency_key"])
        if status is not InvocationStatus.SUCCEEDED:
            raise ToolInvocationConflict(status.value)
        if row["result"] is None:
            raise ToolInvocationResultUnavailable()
        return ToolResult(tool_name=row["tool_name"], content=row["result"])

    async def _is_approved(
        self,
        tenant_id: UUID,
        tool_name: str,
        digest: str,
        approval_id: UUID | None,
    ) -> bool:
        async with tenant_transaction(self._engine, tenant_id) as conn:
            repo = ToolApprovalRepository(conn, tenant_id)
            if approval_id is not None:
                row = await repo.get(approval_id)
                if row is None:
                    return False
                return (
                    row["status"] == ApprovalStatus.APPROVED.value
                    and row["tool_name"] == tool_name
                    and row["arguments_digest"] == digest
                    and row["expires_at"] > datetime.now(UTC)
                )
            return await repo.find_approved(tool_name, digest) is not None

    async def _finish(
        self,
        tenant_id: UUID,
        invocation_id: UUID,
        status: InvocationStatus,
        *,
        result: Any | None = None,
        error_code: str | None = None,
    ) -> None:
        try:
            async with tenant_transaction(self._engine, tenant_id) as conn:
                await ToolInvocationRepository(conn, tenant_id).finish(
                    invocation_id, status=status, result=result, error_code=error_code
                )
        except ToolInvocationStateConflict:
            # The original invocation outcome is authoritative; never mask it.
            return

    @staticmethod
    def _audit_result(content: Any) -> Any | None:
        try:
            encoded = json.dumps(
                content,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
                ensure_ascii=True,
            )
        except (TypeError, ValueError):
            return None
        if len(encoded.encode("utf-8")) > MAX_AUDIT_RESULT_BYTES:
            return None
        return json.loads(encoded)
