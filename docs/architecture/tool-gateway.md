# Tool gateway

The in-process tool gateway foundation is implemented; real tool access is not. `ToolGateway` is the only supported path for tool discovery and invocation, and it exposes no MCP connection, network adapter, HTTP route, or agent-runtime integration yet.

## Enforced today

- **Deny by default.** `AllowlistToolPolicy` requires an explicit per-tenant allowlist. Authorization runs before registry lookup, so a tenant cannot probe the registry through error differences; discovery returns only allowed definitions.
- **Static registration.** `InMemoryToolRegistry` accepts in-process tools only. It rejects duplicate names, input schemas that do not describe an object, and invalid JSON Schema.
- **Schema validation.** Arguments are validated against the tool's Draft 2020-12 input schema before execution. Remote `$ref` retrieval is disabled, so validation cannot make network calls; unresolvable references fail closed. Validator errors report the failing path but never echo argument values.
- **Approval denial.** Tools marked `requires_approval` are always denied with `ToolApprovalRequired`; no approval workflow exists, so gated tools cannot run.
- **Timeouts and normalized errors.** Each tool has a bounded timeout (0 < seconds <= 30). Timeouts and unexpected failures surface as gateway errors whose messages exclude arguments and tool output.

Contracts live in `packages/schemas/tools.py` (`ToolDefinition`, `ToolResult`); gateway errors, the registry, and the gateway live in `apps/tool_gateway/`. Tool output is returned as untrusted content and must not be treated as instructions.

## Not implemented

Before real tool access, the gateway still needs: MCP servers and network egress policy, SSRF defenses, credential and secret injection outside model context, audit and invocation persistence, idempotency keys, a real approval workflow with external authorization, per-tenant quota and rate limits, output size and content limits, and API/runtime callers. None of these should be inferred from the current foundation.
