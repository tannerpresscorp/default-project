from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schemas.budgets import BudgetLimits, BudgetStatus
from packages.usage.budget import BudgetExceeded, BudgetService, current_month_start


class StubBudgetService(BudgetService):
    def __init__(self, status: BudgetStatus) -> None:
        self._status = status

    async def status(self, tenant_id) -> BudgetStatus:  # noqa: ANN001 - fixture stub
        return self._status


def status(**overrides) -> BudgetStatus:
    values = {
        "monthly_cost_micros": None,
        "monthly_tokens": None,
        "events": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_micros": 0,
    }
    values.update(overrides)
    return BudgetStatus(**values)


def test_current_month_start_is_the_first_instant_of_the_utc_month():
    now = datetime(2026, 11, 7, 13, 45, 59, 123456, tzinfo=UTC)
    assert current_month_start(now) == datetime(2026, 11, 1, tzinfo=UTC)


@pytest.mark.anyio
async def test_absent_limits_are_unlimited():
    service = StubBudgetService(status(cost_micros=10**12, input_tokens=10**12))
    await service.check(uuid4())


@pytest.mark.anyio
async def test_cost_limit_blocks_at_the_configured_threshold():
    allowed = StubBudgetService(status(monthly_cost_micros=100, cost_micros=99))
    blocked = StubBudgetService(status(monthly_cost_micros=100, cost_micros=100))
    await allowed.check(uuid4())
    with pytest.raises(BudgetExceeded):
        await blocked.check(uuid4())


@pytest.mark.anyio
async def test_token_limit_counts_input_and_output_tokens():
    allowed = StubBudgetService(status(monthly_tokens=100, input_tokens=40, output_tokens=59))
    blocked = StubBudgetService(status(monthly_tokens=100, input_tokens=40, output_tokens=60))
    await allowed.check(uuid4())
    with pytest.raises(BudgetExceeded):
        await blocked.check(uuid4())


def test_budget_contracts_reject_negative_and_excessive_values():
    with pytest.raises(ValidationError):
        BudgetLimits(monthly_cost_micros=-1)
    with pytest.raises(ValidationError):
        BudgetLimits(monthly_tokens=-1)
    with pytest.raises(ValidationError):
        BudgetLimits(monthly_tokens=10**12 + 1)
    with pytest.raises(ValidationError):
        BudgetLimits(extra_field=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        status(input_tokens=-1)
