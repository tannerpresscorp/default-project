import asyncio

import pytest
from pydantic import ValidationError

from apps.eval_service.datasets import OFFLINE_SMOKE_CASES
from apps.eval_service.runner import EvalRunner
from packages.model_clients.fake import DeterministicModelProvider
from packages.schemas.evals import EvalCase


async def offline_generate(prompt: str) -> str:
    from packages.model_clients.contracts import ModelMessage, ModelRequest

    response = await DeterministicModelProvider().generate(
        "offline-chat", ModelRequest(messages=(ModelMessage(role="user", content=prompt),))
    )
    return response.content


@pytest.mark.anyio
async def test_fixed_offline_cases_pass_deterministically():
    runner = EvalRunner(offline_generate)

    first = await runner.run(OFFLINE_SMOKE_CASES)
    second = await runner.run(OFFLINE_SMOKE_CASES)

    assert first == second
    assert first.passed == first.total == 2
    assert all(
        result.output and result.output.startswith("[offline-chat]") for result in first.results
    )


@pytest.mark.anyio
async def test_failed_expectation_is_reported_without_raising():
    runner = EvalRunner(offline_generate)
    case = EvalCase(name="mismatch", prompt="hello", expected_substring="not present")

    report = await runner.run((case,))

    assert report.passed == 0
    assert report.total == 1
    assert report.results[0].passed is False
    assert report.results[0].error is None


@pytest.mark.anyio
async def test_generation_errors_are_normalized():
    async def fail(prompt: str) -> str:
        raise RuntimeError("secret=leaked")

    report = await EvalRunner(fail).run(OFFLINE_SMOKE_CASES[:1])

    assert report.results[0].error == "generation_failed"
    assert "secret" not in report.model_dump_json()


@pytest.mark.anyio
async def test_timeouts_are_bounded():
    async def slow(prompt: str) -> str:
        await asyncio.sleep(1)
        return prompt

    report = await EvalRunner(slow, timeout_seconds=0.01).run(OFFLINE_SMOKE_CASES[:1])

    assert report.results[0].error == "timeout"
    assert report.results[0].passed is False


def test_eval_contracts_are_bounded_and_forbid_extra_fields():
    with pytest.raises(ValidationError):
        EvalCase(name="Bad Name", prompt="p", expected_substring="e")
    with pytest.raises(ValidationError):
        EvalCase(name="ok", prompt="", expected_substring="e")
    with pytest.raises(ValidationError):
        EvalCase(name="ok", prompt="p", expected_substring="")
    with pytest.raises(ValidationError):
        EvalCase(name="ok", prompt="p", expected_substring="e", extra=True)
    with pytest.raises(ValueError):
        EvalRunner(offline_generate, timeout_seconds=0)
    with pytest.raises(ValueError):
        EvalRunner(offline_generate, timeout_seconds=61)
