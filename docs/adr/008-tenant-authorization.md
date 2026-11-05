# ADR-008: Multi-tenant authorization

## Context
Tenant identity must be verified and isolation cannot rely on a single application filter.
## Decision
Use trusted signed tenant claims, tenant-scoped repositories, transaction-local PostgreSQL RLS and tenant-aware foreign keys. Keep authorization separate and add a replaceable policy layer for tools in Phase 3.
## Alternatives considered
Client-provided tenant IDs or application filters alone are insufficient; per-tenant databases add operational cost.
## Consequences
The identity provider must attest membership; separate application and migration roles are mandatory. No resource-level policy engine or independent membership store is implemented yet.
## Operational risks
Incorrect issuer claims, bypass-capable roles, SQL injection and RLS policy drift can defeat isolation; RLS does not isolate a compromised application role that can set another tenant context.
