# Sandbox manager

Phase 6 implements a deny-by-default sandbox boundary. It does **not** execute code.

- `apps/sandbox_manager/manager.py` authorizes the tenant, applies a timeout and bounds captured output.
- `apps/sandbox_manager/backend.py` defines the `SandboxBackend` protocol and `DisabledSandboxBackend`, which always denies. A real adapter (microVM, gVisor or hardened Kubernetes job) is not implemented.
- `apps/sandbox_manager/policy.py` defaults to `DenyAllSandboxPolicy`; `AllowlistSandboxPolicy` enables explicit tenants only.

No code, shell, network or file access is available through this package yet. See [docs/architecture/sandbox.md](../../docs/architecture/sandbox.md).
