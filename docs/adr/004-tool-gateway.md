# ADR-004: Governed MCP and tool gateway

## Context
Model-generated tool calls are untrusted and may have privileged side effects.
## Decision
Centralize tool access, authentication, policy, validation and audit behind a gateway; implement in Phase 3.
## Alternatives considered
Direct agent connections simplify prototypes but bypass centralized governance.
## Consequences
Tools need trust classification, explicit allowlists, timeout, approval and idempotency contracts.
## Operational risks
Gateway compromise, SSRF, leaked credentials, duplicate mutations and untrusted MCP servers need layered controls.
