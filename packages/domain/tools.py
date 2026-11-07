"""Tool invocation and approval state shared by code and persistence."""

from enum import StrEnum
from typing import Final


class InvocationStatus(StrEnum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"


TERMINAL_INVOCATION_STATUSES: Final[frozenset[InvocationStatus]] = frozenset(
    {InvocationStatus.SUCCEEDED, InvocationStatus.FAILED, InvocationStatus.DENIED}
)


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"


TERMINAL_APPROVAL_STATUSES: Final[frozenset[ApprovalStatus]] = frozenset(
    {ApprovalStatus.APPROVED, ApprovalStatus.DENIED, ApprovalStatus.EXPIRED}
)
