# Evaluations

Phase 7 provides a deterministic runner and a fixed offline smoke dataset. The point is repeatable verification of the wiring between a system under test and the evaluation contract, not a claim about model quality.

## Contract

`EvalCase` has a stable name, a bounded prompt and an expected substring. `EvalReport` contains one `EvalCaseResult` per case plus `passed` and `total`. A case passes only when the expected substring appears in the bounded output. Generation errors become `generation_failed`; timeouts become `timeout`. Neither includes the original exception text.

## Offline dataset

`apps/eval_service/datasets.py` contains two cases for the deterministic provider. Both assert the provider's `[offline-chat]` prefix, so they verify the pipeline rather than semantic quality. The unit tests assert that two runs produce identical reports.

## Not implemented

There are no vendor-backed evaluations, datasets with secrets, semantic graders, LLM-as-judge, statistical confidence intervals, regressions gates or stored evaluation history. Adding any of those requires a separate cost, privacy and reproducibility review.
