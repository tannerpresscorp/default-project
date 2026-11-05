# ADR-007: Sandbox isolation model

## Context
Generated code is hostile and cannot execute inside an agent runtime container.
## Decision
Use a separate sandbox manager interface, with isolated ephemeral execution and restricted credentials, resources and network; implement in Phase 6.
## Alternatives considered
In-process execution is unsafe; microVMs, gVisor and hardened jobs are possible adapters, not yet selected or implemented.
## Consequences
Execution must be attributable, bounded and isolated; Kubernetes alone is not a complete security boundary.
## Operational risks
Sandbox escape, kernel vulnerabilities, egress bypass and capacity exhaustion require defense in depth and incident response.
