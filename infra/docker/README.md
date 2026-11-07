# Docker

The repository includes gated Helm manifests and an operations runbook, but no platform application image is committed or built in CI yet.

A deployer that builds an image must pin a Python 3.12 base image by digest, install `requirements-platform.txt`, run as a non-root user, use a read-only root filesystem, and provide no build secrets. The image must not include `.venv`, tests, `.env` files or repository credentials. Do not claim an image is production-ready until it has been built, scanned and exercised in the target environment.
