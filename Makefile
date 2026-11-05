PYTHON ?= .venv-platform/bin/python
COMPOSE = docker compose -f infra/local/compose.yaml

.PHONY: dev test lint typecheck migrate integration-test
dev:
	$(COMPOSE) up -d --wait postgres redis

test:
	$(PYTHON) -m pytest -c pyproject.toml tests/unit

lint:
	$(PYTHON) -m ruff check apps packages tests
	$(PYTHON) -m ruff format --check apps packages tests

typecheck:
	$(PYTHON) -m mypy

migrate:
	$(PYTHON) -m alembic upgrade head

integration-test:
	@test -n "$$PLATFORM_TEST_DATABASE_URL" || (echo "PLATFORM_TEST_DATABASE_URL is required"; exit 1)
	$(PYTHON) -m pytest -c pyproject.toml tests/integration
