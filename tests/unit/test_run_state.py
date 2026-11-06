import pytest

from packages.domain.runs import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    InvalidRunTransition,
    RunStatus,
    can_transition,
    ensure_transition,
    is_terminal,
)

EXPECTED_TRANSITIONS = {
    RunStatus.PENDING: {
        RunStatus.RUNNING,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    },
    RunStatus.RUNNING: {
        RunStatus.WAITING_FOR_TOOL,
        RunStatus.WAITING_FOR_APPROVAL,
        RunStatus.RETRYING,
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    },
    RunStatus.WAITING_FOR_TOOL: {
        RunStatus.RUNNING,
        RunStatus.WAITING_FOR_APPROVAL,
        RunStatus.RETRYING,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    },
    RunStatus.WAITING_FOR_APPROVAL: {
        RunStatus.RUNNING,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    },
    RunStatus.RETRYING: {
        RunStatus.RUNNING,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.TIMED_OUT,
    },
    RunStatus.SUCCEEDED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
    RunStatus.TIMED_OUT: set(),
}

EXPECTED_TERMINAL = {
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
    RunStatus.TIMED_OUT,
}


def test_transition_map_matches_the_documented_contract():
    assert set(ALLOWED_TRANSITIONS) == set(RunStatus)
    for current, targets in EXPECTED_TRANSITIONS.items():
        assert ALLOWED_TRANSITIONS[current] == frozenset(targets)
    assert TERMINAL_STATUSES == frozenset(EXPECTED_TERMINAL)


def test_every_status_pair_is_decided_explicitly():
    for current in RunStatus:
        for target in RunStatus:
            allowed = target in EXPECTED_TRANSITIONS[current]
            assert can_transition(current, target) is allowed
            if allowed:
                assert ensure_transition(current, target) is target
            else:
                with pytest.raises(InvalidRunTransition) as error:
                    ensure_transition(current, target)
                assert error.value.current is current
                assert error.value.target is target


def test_terminal_statuses_cannot_leave_their_state():
    for status in TERMINAL_STATUSES:
        assert is_terminal(status)
        assert ALLOWED_TRANSITIONS[status] == frozenset()


def test_non_terminal_statuses_are_not_terminal():
    for status in set(RunStatus) - TERMINAL_STATUSES:
        assert not is_terminal(status)
