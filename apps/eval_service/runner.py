"""Deterministic evaluation runner for offline and provider-neutral checks."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from packages.schemas.evals import EvalCase, EvalCaseResult, EvalReport

MAX_REPORT_OUTPUT_CHARS = 2_000
Generate = Callable[[str], Awaitable[str]]


class EvalRunner:
    """Run fixed cases through one system under test with bounded output."""

    def __init__(self, generate: Generate, *, timeout_seconds: float = 10.0) -> None:
        if not 0 < timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be greater than 0 and at most 60")
        self._generate = generate
        self._timeout_seconds = timeout_seconds

    async def run(self, cases: Sequence[EvalCase]) -> EvalReport:
        results = tuple([await self._run_case(case) for case in cases])
        return EvalReport(
            results=results,
            passed=sum(1 for result in results if result.passed),
            total=len(results),
        )

    async def _run_case(self, case: EvalCase) -> EvalCaseResult:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                output = await self._generate(case.prompt)
        except TimeoutError:
            return EvalCaseResult(name=case.name, passed=False, error="timeout")
        except Exception:
            return EvalCaseResult(name=case.name, passed=False, error="generation_failed")
        bounded = output[:MAX_REPORT_OUTPUT_CHARS]
        return EvalCaseResult(
            name=case.name,
            passed=case.expected_substring in bounded,
            output=bounded,
        )
