# Sandbox

Phase 6 implements the authorization and lifecycle boundary for code execution, not execution itself. `SandboxManager` is the only supported entry point. It denies by default, requires an explicit per-tenant allowlist, enforces a caller-provided timeout, normalizes unexpected backend failures and bounds stdout/stderr to 64 KiB by default.

| Component | Status |
| --- | --- |
| `SandboxRequest` / `SandboxResult` contracts | Implemented; Python only, 100,000-character code, 60-second maximum |
| `SandboxPolicy` | Implemented; `DenyAllSandboxPolicy` is the default |
| `SandboxManager` | Implemented; authorization, timeout, error normalization, output truncation |
| `SandboxBackend` | Protocol only; `DisabledSandboxBackend` always denies |
| Real isolated execution | Not implemented |

## Security requirements for an adapter

A future adapter must provide isolation at least as strong as a separate VM or gVisor sandbox, run without platform credentials, use a read-only root filesystem and non-root user, deny all network egress by default, cap CPU/memory/processes/disk, and destroy the environment after each request. Kubernetes alone is not a complete security boundary. Execution must remain attributable to a tenant and must never run in the API or workflow worker process.

## Explicit non-goals

The current package has no container runtime, no Kubernetes client, no shell, no package installation, no artifact upload and no network access. Those omissions are deliberate, not unfinished wiring.
