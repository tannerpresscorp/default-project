# Helm

`agent-platform/` is a gated starting point for deploying the FastAPI control plane and Temporal worker. It renders nothing unless `global.enabled` and a component are explicitly enabled. CI lints the chart and renders it with gated and enabled values; it is never applied.

It is **not** production-ready. The chart has no validated container image, ingress, certificate, secret store integration, migration job, autoscaling, service mesh or cluster-specific policy, and it is not validated against a live cluster. Treat the chart as a reviewed baseline, not an operational deployment.

```sh
helm template agent-platform infra/helm/agent-platform \
  --set global.enabled=true \
  --set api.enabled=true \
  --set global.image.repository=registry.example/agent-platform \
  --set global.image.tag=sha256-REPLACE \
  --set api.existingSecret=agent-platform-secrets
```

## Validate and deploy with the repository tooling

Start from [`agent-platform/values.example.yaml`](agent-platform/values.example.yaml) and keep the real values file outside the repository. The Makefile requires an explicit values file for rendering and deployment, forces `global.enabled=true`, and overrides the image repository and tag. The deployment targets use Helm 4.x flags.

```sh
HELM_VALUES=../deploy/agent-platform.yaml make helm-lint
HELM_VALUES=../deploy/agent-platform.yaml make helm-template
HELM_VALUES=../deploy/agent-platform.yaml \
  IMAGE_REPOSITORY=registry.example/agent-platform \
  IMAGE_TAG=sha256-... \
  HELM_CONTEXT=staging \
  make deploy
```

On Windows use `.\scripts\platform.ps1 helm-lint -Values ...`, `helm-template` or `deploy`. `deploy` runs `helm upgrade --install --rollback-on-failure --wait` against the current or explicitly supplied Kubernetes context. CI only lints and renders the chart; it never applies it.

## Local smoke deployment

A throwaway k3s cluster in the same Linux VM (or any local cluster) can exercise the chart end to end. This is a smoke test, not a production deployment:

1. Build the image and import it into the cluster's container runtime, for example `docker save agent-platform:smoke | sudo k3s ctr images import -`.
2. Create a namespace and a secret with `PLATFORM_DATABASE_URL` and the OIDC variables. A pod cannot use `127.0.0.1` for PostgreSQL; use the host/IP reachable from the cluster.
3. Use a values file outside the repository that sets `api.enabled=true`, `api.existingSecret`, `global.image.pullPolicy=Never` and, for a minimal test, disables `networkPolicy` and `podDisruptionBudget`.
4. Deploy with an explicit tag and context:

```powershell
.\scripts\platform.ps1 deploy -Values C:\path\to\values.local.yaml -ImageTag smoke -KubeContext platform-vm
kubectl -n agent-platform get pods,svc
kubectl -n agent-platform port-forward svc/agent-platform-agent-platform-api 18001:8001
```

`/health/live` and `/health/ready` should both return `200` when the database, RLS role and OIDC configuration are valid; `/metrics` is also exposed. Remove the release and namespace when finished.

See [the operations runbook](../../docs/runbooks/platform-operations.md) before applying anything to a real cluster.
