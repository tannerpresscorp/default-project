# Tool gateway

Not implemented in Phase 1. Agents must not connect directly to arbitrary MCP servers. Phase 3 should add tool discovery, explicit tenant-aware allowlists, external authorization, schema validation, audit and invocation persistence. Privileged actions need approval and idempotency; secrets must remain outside model context. Network restrictions, timeout and SSRF defenses are required before real tool access.
