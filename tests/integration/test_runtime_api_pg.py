"""Runtime API, budgets and retrieval against migrated PostgreSQL."""

import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.main import create_app
from packages.auth.identity import Principal
from packages.config.settings import Settings
from packages.persistence.database import tenant_transaction


class FakeVerifier:
    def __init__(self, tenant_id: UUID) -> None:
        self._tenant_id = tenant_id

    async def verify(self, token: str) -> Principal:
        if token != "valid":
            from packages.auth.identity import AuthenticationError

            raise AuthenticationError("invalid")
        return Principal(subject="alice", tenant_id=self._tenant_id)


class FakeDispatcher:
    def __init__(self) -> None:
        self.started: list[dict[str, str]] = []
        self.cancelled: list[UUID] = []

    async def start(
        self, *, tenant_id: UUID, run_id: UUID, prompt: str, logical_model: str
    ) -> None:
        self.started.append(
            {
                "tenant_id": str(tenant_id),
                "run_id": str(run_id),
                "prompt": prompt,
                "logical_model": logical_model,
            }
        )

    async def cancel(self, *, tenant_id: UUID, run_id: UUID) -> None:
        self.cancelled.append(run_id)


async def _seed(database_url: str, tenant_id: UUID) -> tuple[UUID, UUID]:
    engine = create_async_engine(database_url)
    agent_id, version_id = uuid4(), uuid4()
    try:
        async with tenant_transaction(engine, tenant_id) as conn:
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, 'runtime')"),
                {"id": tenant_id},
            )
            await conn.execute(
                text("INSERT INTO agents (id, tenant_id, name) VALUES (:id, :tenant, 'agent')"),
                {"id": agent_id, "tenant": tenant_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO agent_versions (id, tenant_id, agent_id, code, prompt, "
                    "model_policy, tool_policy, retrieval_config) "
                    "VALUES (:id, :tenant, :agent, 'sha', 'p', 'm', 't', 'r')"
                ),
                {"id": version_id, "tenant": tenant_id, "agent": agent_id},
            )
    finally:
        await engine.dispose()
    return agent_id, version_id


def test_runtime_run_lifecycle_budget_and_retrieval(database_url):
    tenant_id = uuid4()
    agent_id, version_id = asyncio.run(_seed(database_url, tenant_id))
    dispatcher = FakeDispatcher()
    app = create_app(
        Settings(otel_enabled=False, database_url=database_url),
        verifier=FakeVerifier(tenant_id),
        run_dispatcher=dispatcher,
    )
    headers = {"Authorization": "Bearer valid"}
    payload = {
        "agent_id": str(agent_id),
        "agent_version_id": str(version_id),
        "prompt": "hello runtime",
    }

    with TestClient(app) as client:
        assert client.post("/v1/runs", json=payload).status_code == 401

        created = client.post("/v1/runs", headers=headers, json=payload)
        assert created.status_code == 202
        run = created.json()
        assert run["status"] == "PENDING"
        assert dispatcher.started[0]["run_id"] == run["id"]
        assert dispatcher.started[0]["prompt"] == "hello runtime"

        fetched = client.get(f"/v1/runs/{run['id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["agent_id"] == str(agent_id)

        listed = client.get("/v1/runs", headers=headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["runs"]] == [run["id"]]

        missing = client.get(f"/v1/runs/{uuid4()}", headers=headers)
        assert missing.status_code == 404

        mismatched = client.post(
            "/v1/runs",
            headers=headers,
            json={**payload, "agent_version_id": str(uuid4())},
        )
        assert mismatched.status_code == 422

        cancelled = client.post(f"/v1/runs/{run['id']}/cancel", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"
        assert dispatcher.cancelled == [UUID(run["id"])]

        again = client.post(f"/v1/runs/{run['id']}/cancel", headers=headers)
        assert again.status_code == 409

        budget = client.put(
            "/v1/budget",
            headers=headers,
            json={"monthly_tokens": 0, "monthly_cost_micros": None},
        )
        assert budget.status_code == 200
        assert budget.json()["monthly_tokens"] == 0
        assert client.get("/v1/budget", headers=headers).json()["events"] == 0

        rejected = client.post("/v1/runs", headers=headers, json=payload)
        assert rejected.status_code == 429
        assert rejected.json()["error"]["code"] == "http_429"

        unlimited = client.put("/v1/budget", headers=headers, json={})
        assert unlimited.status_code == 200
        assert unlimited.json()["monthly_tokens"] is None
        assert client.post("/v1/runs", headers=headers, json=payload).status_code == 202

        ingested = client.post(
            "/v1/retrieval/documents",
            headers=headers,
            json={
                "documents": [
                    {"collection": "docs", "source": "handbook", "content": "alpha beta gamma"}
                ]
            },
        )
        assert ingested.status_code == 201
        assert len(ingested.json()["ids"]) == 1

        results = client.post(
            "/v1/retrieval/search",
            headers=headers,
            json={"query": "alpha beta gamma", "collection": "docs", "limit": 3},
        )
        assert results.status_code == 200
        matches = results.json()["matches"]
        assert len(matches) == 1
        assert matches[0]["source"] == "handbook"

        with client.stream("GET", f"/v1/runs/{run['id']}/events", headers=headers) as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())
        assert "event: status" in body
        assert '"status":"CANCELLED"' in body
        assert "event: end" in body

        with client.stream("GET", f"/v1/runs/{uuid4()}/events", headers=headers) as stream:
            assert stream.status_code == 200
            body = "".join(stream.iter_text())
        assert '{"code":"not_found"}' in body

        metrics = client.get("/metrics").text
        assert "platform_runs_submitted_total 2" in metrics
        assert "platform_run_cancellations_total 1" in metrics
        assert "platform_budget_rejections_total 1" in metrics
        assert "platform_retrieval_ingestions_total 1" in metrics
        assert "platform_retrieval_searches_total 1" in metrics
