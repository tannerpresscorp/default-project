# ADR-003: Centralized model gateway

## Context
Provider behavior, spend and reliability differ.
## Decision
Route vendor calls through a logical gateway with isolated adapters; implement in Phase 2.
## Alternatives considered
Direct provider SDK calls in each service duplicate policy and tracking.
## Consequences
One boundary manages routing, observability, structured output hooks and usage without pretending providers are identical.
## Operational risks
Gateway outages, provider degradation, routing misconfiguration and cost escalation need limits and fallback policies.
