"""Fixed offline evaluation dataset; it contains no production or vendor claims."""

from packages.schemas.evals import EvalCase

OFFLINE_SMOKE_CASES = (
    EvalCase(
        name="echo-prefix",
        prompt="deterministic evaluation",
        expected_substring="[offline-chat] deterministic evaluation",
    ),
    EvalCase(
        name="short-prompt",
        prompt="hello",
        expected_substring="[offline-chat] hello",
    ),
)
