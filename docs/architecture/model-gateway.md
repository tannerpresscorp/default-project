# Model gateway

Not implemented in Phase 1. Phase 2 should introduce a provider-neutral interface, logical model routing and a deterministic fake provider behind one gateway boundary. Provider-specific behavior must stay in adapters; no other service should call model vendors directly. Retry, timeout, quotas, accounting and safe telemetry are required before production use.
