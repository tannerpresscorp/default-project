# Docker

`Dockerfile` builds the shared FastAPI control-plane and Temporal worker image. CI builds it and runs non-root, read-only health smoke tests; the image is not published.

The image pins the Python 3.12 base by digest, installs `requirements-platform.txt` into a virtual environment, runs as UID/GID `10001`, and expects a read-only root filesystem with a writable `/tmp`. Tests, docs, `.env` files and repository credentials are excluded by `.dockerignore`.

The image is Linux-only. On Windows, use a Linux Docker engine: Docker Desktop on a client OS, or a Hyper-V Linux VM selected with `docker context use <name>` on Windows Server (WSL2 is unavailable there). See [the development guide](../../docs/architecture/development.md#windows-server-with-a-linux-vm).

## Build

```sh
make image
# or:
docker build -f infra/docker/Dockerfile -t agent-platform:local .
```

PowerShell:

```powershell
.\scripts\platform.ps1 build
```

Use an immutable tag or digest when publishing:

```sh
IMAGE_REPOSITORY=registry.example/agent-platform IMAGE_TAG=sha256-... make image
```

## Run locally

The Compose stack defines `postgres` and `redis` services plus `api` and `worker` services behind profiles. The API profile uses the same image and a fixed in-network database URL. PostgreSQL is built from a small derivative image (`infra/local/postgres/Dockerfile`) so `postgres-init.sql` ships in the build context instead of relying on a host bind mount, which would not resolve when Docker runs in a remote VM.

```sh
make run         # PostgreSQL + Redis, migrations, then the API on http://127.0.0.1:8001
make run-worker  # PostgreSQL + Redis, then the Temporal worker
make logs
make stop
```

On a remote Linux Docker host the published API port belongs to that host. The PowerShell wrapper exports `PLATFORM_BIND_ADDRESS=0.0.0.0` for `run` and prints the Docker host's address; set `PLATFORM_DB_BIND_ADDRESS=0.0.0.0` when PostgreSQL must be reachable from another host, such as a cluster in the same VM. Both variables default to `127.0.0.1`.

PowerShell:

```powershell
.\scripts\platform.ps1 run
.\scripts\platform.ps1 run-worker
```

Without OIDC configuration the API still answers `/health/live`, but `/health/ready` and all `/v1` routes fail closed with `503`. The worker expects Temporal at `host.docker.internal:7233`; override `PLATFORM_TEMPORAL_ADDRESS` if it runs elsewhere. When the API container needs Temporal, point it at `host.docker.internal:7233` too rather than `127.0.0.1`.

Local database passwords are intentionally public and loopback-bound. Never reuse them outside local development. Do not claim the image is production-ready until it has been scanned and exercised in the target environment.
