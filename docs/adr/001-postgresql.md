# ADR-001: PostgreSQL as primary store

## Context
Platform records need transactional durability and tenant isolation.
## Decision
Use managed PostgreSQL in production with SQLAlchemy and Alembic; SQLite remains only for the existing Django application.
## Alternatives considered
SQLite lacks the required production isolation and concurrency; distributed databases add operational complexity.
## Consequences
Relational constraints, transactions and RLS become first-class; database lifecycle and backups are external responsibilities.
## Operational risks
Connection exhaustion, privileged role drift, migrations, backup recovery and degraded performance require operational controls.
