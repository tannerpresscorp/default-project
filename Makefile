PYTHON ?= .venv-platform/bin/python
IMAGE_REPOSITORY ?= agent-platform
IMAGE_TAG ?= local
IMAGE ?= $(IMAGE_REPOSITORY):$(IMAGE_TAG)
PLATFORM_BIND_ADDRESS ?= 127.0.0.1
COMPOSE = PLATFORM_IMAGE=$(IMAGE) PLATFORM_BIND_ADDRESS=$(PLATFORM_BIND_ADDRESS) docker compose -f infra/local/compose.yaml
HELM_CHART ?= infra/helm/agent-platform
HELM_RELEASE ?= agent-platform
HELM_NAMESPACE ?= agent-platform
HELM_VALUES ?=
HELM_TIMEOUT ?= 10m
HELM_CONTEXT ?=

.PHONY: dev db-up build build-web image run run-worker stop down logs worker \
	test lint typecheck migrate migrate-container integration-test \
	helm-lint helm-template deploy

dev: db-up

db-up:
	$(COMPOSE) up -d --wait postgres redis

build: image

build-web:
	pnpm --filter web build

image:
	docker build -f infra/docker/Dockerfile -t $(IMAGE) .

# Run the API in a read-only container against the local Compose database.
# Readiness still requires OIDC and a safe database role; liveness does not.
run: db-up migrate-container
	$(COMPOSE) --profile api up -d --build --wait api
	@echo "API: http://127.0.0.1:8001 (liveness: /health/live)"

# Requires a Temporal server reachable from the container. The default is
# host.docker.internal:7233; override PLATFORM_TEMPORAL_ADDRESS if needed.
run-worker: db-up migrate-container
	$(COMPOSE) --profile worker up -d --build worker
	@echo "Worker started; it requires PLATFORM_TEMPORAL_ADDRESS to be reachable."

stop:
	$(COMPOSE) --profile api --profile worker stop api worker

down:
	$(COMPOSE) --profile api --profile worker down

logs:
	$(COMPOSE) --profile api --profile worker logs -f api worker

worker:
	$(PYTHON) -m apps.workflow_worker.worker

test:
	$(PYTHON) -m pytest -c pyproject.toml tests/unit

lint:
	$(PYTHON) -m ruff check apps packages tests
	$(PYTHON) -m ruff format --check apps packages tests

typecheck:
	$(PYTHON) -m mypy

migrate:
	$(PYTHON) -m alembic upgrade head

migrate-container: db-up
	$(COMPOSE) --profile api run --rm --no-deps --build \
		-e PLATFORM_MIGRATION_DATABASE_URL='postgresql+asyncpg://platform_migrator:local_migrator_only@postgres:5432/platform' \
		api python -m alembic upgrade head

integration-test:
	@test -n "$$PLATFORM_TEST_DATABASE_URL" || (echo "PLATFORM_TEST_DATABASE_URL is required"; exit 1)
	$(PYTHON) -m pytest -c pyproject.toml tests/integration

helm-lint:
	helm lint --strict $(HELM_CHART) $(if $(strip $(HELM_VALUES)),-f $(HELM_VALUES),)

helm-template:
	@test -n "$(strip $(HELM_VALUES))" || (echo "HELM_VALUES is required; see infra/helm/agent-platform/values.example.yaml"; exit 1)
	helm template $(HELM_RELEASE) $(HELM_CHART) \
		--namespace $(HELM_NAMESPACE) \
		-f $(HELM_VALUES) \
		--set global.enabled=true \
		--set-string global.image.repository=$(IMAGE_REPOSITORY) \
		--set-string global.image.tag=$(IMAGE_TAG)

deploy: helm-lint
	@test -n "$(strip $(HELM_VALUES))" || (echo "HELM_VALUES is required; see infra/helm/agent-platform/values.example.yaml"; exit 1)
	@test -n "$(IMAGE_REPOSITORY)" || (echo "IMAGE_REPOSITORY is required"; exit 1)
	@test -n "$(IMAGE_TAG)" || (echo "IMAGE_TAG is required"; exit 1)
	@test "$(IMAGE_TAG)" != "local" || (echo "IMAGE_TAG=local is not deployable; set an immutable tag or digest"; exit 1)
	helm upgrade --install $(HELM_RELEASE) $(HELM_CHART) \
		--namespace $(HELM_NAMESPACE) --create-namespace \
		-f $(HELM_VALUES) \
		--set global.enabled=true \
		--set-string global.image.repository=$(IMAGE_REPOSITORY) \
		--set-string global.image.tag=$(IMAGE_TAG) \
		$(if $(strip $(HELM_CONTEXT)),--kube-context $(HELM_CONTEXT),) \
		--rollback-on-failure --wait --timeout $(HELM_TIMEOUT)
