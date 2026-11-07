# Tool gateway

The in-process tool gateway foundation is implemented; real tool access is not. `ToolGateway` is the only supported path for tool discovery and invocation, and it exposes no MCP connection, network adapter or HTTP route yet. `ToolInvocationService` adds audited, idempotent invocation to the gateway, and `ToolApprovalWorkflow` provides durable human approval for gated tools.

## Enforced today

- **Deny by default.** `AllowlistToolPolicy` requires an explicit per-tenant allowlist. Authorization runs before registry lookup, so a tenant cannot probe the registry through error differences; discovery returns only allowed definitions.
- **Static registration.** `InMemoryToolRegistry` accepts in-process tools only. It rejects duplicate names, input schemas that do not describe an object, and invalid JSON Schema.
- **Schema validation.** Arguments are validated against the tool's Draft 2020-12 input schema before execution. Remote `$ref` retrieval is disabled, so validation cannot make network calls; unresolvable references fail closed. Validator errors report the failing path but never echo argument values.
- **Approval enforcement.** Tools marked `requires_approval` are denied with `ToolApprovalRequired` unless the caller supplies an approval that is `APPROVED`, unexpired, tenant-scoped, and bound to the same tool name and SHA-256 digest of canonical arguments. Raw arguments are never stored in the approval or audit tables.
- **Audit and idempotency.** `ToolInvocationService` inserts a `STARTED` record before execution and finishes it as `SUCCEEDED`, `FAILED` or `DENIED`. An optional idempotency key is unique per tenant and per tool invocation; replaying a completed key returns the stored result without re-executing, while a different argument digest or an in-flight key is rejected. Persisted results are size-bounded and may be omitted when not JSON-serializable.
- **Timeouts and normalized errors.** Each tool has a bounded timeout (0 < seconds <= 30). Timeouts and unexpected failures surface as gateway errors whose messages exclude arguments and tool output; audit rows store only the error class name.

Contracts live in `packages/schemas/tools.py` (`ToolDefinition`, `ToolResult`); gateway errors, the registry, gateway and invocation service live in `apps/tool_gateway/`. Tool output is returned as untrusted content and must not be treated as instructions.

## Not implemented

Before real tool access, the gateway still needs: MCP servers and network egress policy, SSRF defenses, credential and secret injection outside model context, a real external authorization service for approvals, per-tenant quota and rate limits, output content inspection, and API/runtime callers. None of these should be inferred from the current foundation.
