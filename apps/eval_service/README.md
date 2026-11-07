# Evaluation service

Phase 7 implements a deterministic evaluation runner. It does not call vendors or claim production model quality.

- `apps/eval_service/runner.py`: runs fixed `EvalCase` prompts through one async system under test, requires an expected substring, applies a timeout and normalizes failures.
- `apps/eval_service/datasets.py`: a fixed offline smoke dataset for the deterministic model provider.
- `packages/schemas/evals.py`: bounded contracts and a pass/total report.

Outputs are truncated for reports and remain untrusted data. The current checks are smoke tests, not security, safety, quality or regression benchmarks. See [docs/architecture/evaluations.md](../../docs/architecture/evaluations.md).
