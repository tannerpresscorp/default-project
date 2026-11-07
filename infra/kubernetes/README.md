# Kubernetes

The deployment baseline lives in [../helm/agent-platform](../helm/agent-platform). It is gated, renders nothing by default, and is linted and rendered in CI; it is not validated against a live cluster and CI never applies it.

Do not add a second set of raw manifests here. Cluster-specific overlays, ingress, secret-store integration, migration jobs and policy exceptions belong in the deployment repository that owns the target cluster.
