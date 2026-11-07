# Platform operations runbook

This runbook is for a deployer that has chosen to run the gated platform. It does not claim that the repository is production-ready.

## Deployment gate

Do not proceed unless all of the following are true:

1. A container image is built from a pinned Python 3.12 base, scanned, and referenced by immutable digest.
2. PostgreSQL is managed, backed up, encrypted in transit and reachable only over a private path. The runtime role is not superuser, not `BYPASSRLS`, and does not own tables.
3. The `vector` extension is provisioned by an administrator before migrations run.
4. Temporal is a managed or separately operated cluster with persistence, retention and access control. The local dev server is not acceptable.
5. Secrets come from a secret manager, not `values.yaml`, Helm history or container images.
6. NetworkPolicy egress lists only DNS, PostgreSQL and Temporal. Ingress lists only the ingress controller namespace.
7. `helm template` has been reviewed and `helm lint` has no template errors.
8. Readiness has been verified against a staging database; it fails closed without OIDC configuration or safe RLS metadata.

## Migration

Run migrations out of band, never from an application replica:

```sh
PLATFORM_MIGRATION_DATABASE_URL=... python -m alembic upgrade head
PLATFORM_MIGRATION_DATABASE_URL=... python -m alembic check
```

Keep migration credentials out of runtime secrets. Back up the database before a destructive migration. `alembic check` must report no new upgrade operations.

## Rollback

1. Roll back the application image to the previous digest.
2. Do not downgrade a migration automatically; assess data compatibility first.
3. If a migration must be reversed, take a backup, run the corresponding Alembic downgrade in staging, and verify tenant isolation afterward.
4. Restart workers only after the API and database schema are compatible.

## Worker drain and deployment

Temporal workers should stop polling and finish in-flight activities. Use `terminationGracePeriodSeconds` (at least 120) and a rolling update. Verify new workers poll the expected namespace and task queue before scaling old workers down.

## Incident triage

| Symptom | First checks |
| --- | --- |
| Readiness 503 | Database reachability, OIDC discovery/JWKS, RLS metadata for every tenant table |
| Workflow stuck | Temporal UI history, worker health, activity retry budget, database latency |
| Approval not progressing | `tool_approvals` row status/expiry, worker polling, signal delivery |
| Tenant isolation alert | Stop writes, preserve logs, rotate runtime credentials, inspect RLS policies and role membership |
| Token spend anomaly | `usage_records` totals by tenant/model, price book configuration, model gateway routing |
| Sandbox request denied | Expected: no real backend exists. Do not enable execution without a hardened adapter and security review |

## Data handling

Do not place prompts, tool arguments, model output, credentials or database URLs in logs, Sentry events or alerts. Audit rows store digests and error class names only. Treat workflow history and Temporal payloads as sensitive.

## Known limitations

There is no autoscaling, metrics pipeline, alerting, backup automation, disaster-recovery exercise, rate limiting, budget enforcement, sandbox runtime, vendor model adapter or external approval authorization. These are prerequisites for a real production launch.
