from enum import StrEnum
from types import MappingProxyType
from typing import Final, Mapping


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_TOOL = "WAITING_FOR_TOOL"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RETRYING = "RETRYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL_STATUSES: Final[frozenset[RunStatus]] = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    }
)

ALLOWED_TRANSITIONS: Final[Mapping[RunStatus, frozenset[RunStatus]]] = MappingProxyType(
    {
        RunStatus.PENDING: frozenset(
            {
                RunStatus.RUNNING,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.TIMED_OUT,
            }
        ),
        RunStatus.RUNNING: frozenset(
            {
                RunStatus.WAITING_FOR_TOOL,
                RunStatus.WAITING_FOR_APPROVAL,
                RunStatus.RETRYING,
                RunStatus.SUCCEEDED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.TIMED_OUT,
            }
        ),
        RunStatus.WAITING_FOR_TOOL: frozenset(
            {
                RunStatus.RUNNING,
                RunStatus.WAITING_FOR_APPROVAL,
                RunStatus.RETRYING,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.TIMED_OUT,
            }
        ),
        RunStatus.WAITING_FOR_APPROVAL: frozenset(
            {
                RunStatus.RUNNING,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.TIMED_OUT,
            }
        ),
        RunStatus.RETRYING: frozenset(
            {
                RunStatus.RUNNING,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
                RunStatus.TIMED_OUT,
            }
        ),
        RunStatus.SUCCEEDED: frozenset(),
        RunStatus.FAILED: frozenset(),
        RunStatus.CANCELLED: frozenset(),
        RunStatus.TIMED_OUT: frozenset(),
    }
)


class InvalidRunTransition(ValueError):
    """A requested transition is not part of the run state machine."""

    def __init__(self, current: RunStatus, target: RunStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"cannot transition agent run from {current} to {target}")


def is_terminal(status: RunStatus) -> bool:
    return status in TERMINAL_STATUSES


def can_transition(current: RunStatus, target: RunStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def ensure_transition(current: RunStatus, target: RunStatus) -> RunStatus:
    if not can_transition(current, target):
        raise InvalidRunTransition(current, target)
    return target
