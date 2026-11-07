from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from apps.api.main import create_app
from packages.auth.identity import Principal
from packages.config.settings import Settings
from packages.schemas.budgets import BudgetLimits, BudgetStatus
from packages.schemas.retrieval import IngestRequest, RetrievalMatch, SearchRequest

TENANT_ID = uuid4()


class FakeVerifier:
    async def verify(self, token: str) -> Principal:
        if token != "valid":
            from packages.auth.identity import AuthenticationError

            raise AuthenticationError("invalid")
        return Principal(subject="alice", tenant_id=TENANT_ID)


class FakeBudget:
    def __init__(self) -> None:
        self.limits = BudgetLimits()
        self.checked: list[UUID] = []

    async def check(self, tenant_id: UUID) -> None:
        self.checked.append(tenant_id)

    async def status(self, tenant_id: UUID) -> BudgetStatus:
        return BudgetStatus(
            monthly_cost_micros=self.limits.monthly_cost_micros,
            monthly_tokens=self.limits.monthly_tokens,
            events=0,
            input_tokens=0,
            output_tokens=0,
            cost_micros=0,
        )

    async def set_limits(self, tenant_id: UUID, limits: BudgetLimits) -> BudgetStatus:
        self.limits = limits
        return await self.status(tenant_id)


class FakeRetrieval:
    def __init__(self) -> None:
        self.tenant_ids: list[UUID] = []

    async def ingest(self, tenant_id: UUID, request: IngestRequest) -> tuple[UUID, ...]:
        self.tenant_ids.append(tenant_id)
        return tuple(uuid4() for _ in request.documents)

    async def search(self, tenant_id: UUID, request: SearchRequest) -> tuple[RetrievalMatch, ...]:
        self.tenant_ids.append(tenant_id)
        return (
            RetrievalMatch(
                id=uuid4(),
                collection="docs",
                source="handbook",
                content="untrusted content",
                score=0.5,
            ),
        )


def build_client(budget: FakeBudget, retrieval: FakeRetrieval) -> TestClient:
    app = create_app(
        Settings(otel_enabled=False, database_url=None),
        verifier=FakeVerifier(),
        budget_service=budget,
        retrieval_service=retrieval,
    )
    return TestClient(app)


def test_budget_routes_are_authenticated_and_tenant_scoped():
    budget = FakeBudget()
    with build_client(budget, FakeRetrieval()) as client:
        assert client.get("/v1/budget").status_code == 401

        headers = {"Authorization": "Bearer valid"}
        response = client.put(
            "/v1/budget",
            headers=headers,
            json={"monthly_tokens": 500, "monthly_cost_micros": None},
        )
        assert response.status_code == 200
        assert response.json()["monthly_tokens"] == 500
        assert client.get("/v1/budget", headers=headers).json()["monthly_tokens"] == 500


def test_retrieval_routes_forbid_extra_fields_and_stay_bounded():
    retrieval = FakeRetrieval()
    with build_client(FakeBudget(), retrieval) as client:
        headers = {"Authorization": "Bearer valid"}
        response = client.post(
            "/v1/retrieval/documents",
            headers=headers,
            json={"documents": [{"collection": "docs", "source": "a", "content": "b"}]},
        )
        assert response.status_code == 201
        assert len(response.json()["ids"]) == 1

        search = client.post(
            "/v1/retrieval/search", headers=headers, json={"query": "hello", "limit": 5}
        )
        assert search.status_code == 200
        assert search.json()["matches"][0]["source"] == "handbook"

        invalid = client.post(
            "/v1/retrieval/search",
            headers=headers,
            json={"query": "hello", "tenant_id": str(uuid4())},
        )
        assert invalid.status_code == 422

        oversized = client.post(
            "/v1/retrieval/documents",
            headers=headers,
            json={"documents": [{"collection": "docs", "source": "a", "content": ""}]},
        )
        assert oversized.status_code == 422

    assert retrieval.tenant_ids == [TENANT_ID, TENANT_ID]


def test_runtime_fails_closed_without_a_dispatcher():
    with build_client(FakeBudget(), FakeRetrieval()) as client:
        response = client.post(
            "/v1/runs",
            headers={"Authorization": "Bearer valid"},
            json={
                "agent_id": str(uuid4()),
                "agent_version_id": str(uuid4()),
                "prompt": "hello",
            },
        )
        assert response.status_code == 503
