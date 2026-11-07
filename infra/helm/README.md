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

See [the operations runbook](../../docs/runbooks/platform-operations.md) before applying anything to a real cluster.
