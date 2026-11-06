# Model gateway

The in-process model gateway foundation is implemented; no vendor integration exists. `ModelGateway` is the only supported path for model requests, and it currently routes exclusively to a deterministic offline provider.

## Enforced today

- **Static logical routing.** `ModelRouter` maps validated logical model names to a provider adapter and upstream model name. Unknown names are denied with `ModelNotConfigured`; there is no dynamic discovery or vendor lookup.
- **Bounded input.** `ModelRequest` accepts only the `system`, `user`, `assistant` and `tool` roles, caps each message and the total request content, and forbids extra fields. Responses require non-empty content, non-negative usage and an explicit finish reason.
- **Timeouts and normalized errors.** One bounded timeout applies per gateway call (0 < seconds <= 60). Provider timeouts, exceptions and non-response returns surface as gateway errors whose messages exclude prompts, outputs and provider details.
- **Deterministic fake provider.** `DeterministicModelProvider` repeats exactly for the same input, performs no network access, and reports whitespace-based usage. It is for tests and local development only.

Contracts and the fake provider live in `packages/model_clients/`; routing, errors and the gateway live in `apps/model_gateway/`. Model output is untrusted content and must not be treated as instructions. Retries are not implemented, so callers see the first failure.

## Not implemented

Before production use, the gateway still needs: real vendor adapters with isolated credentials, tenant-aware model access policy, retry/backoff policy, per-tenant quotas and rate limits, token accounting and spend persistence, streaming, tool-call payloads, provider capability metadata, prompt safety and moderation hooks, and API/runtime callers. None of these should be inferred from the current foundation.
