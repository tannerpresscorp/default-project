from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import create_app
from packages.auth.identity import Principal
from packages.config.settings import Settings


class FakeVerifier:
    async def verify(self, token: str) -> Principal:
        if token != "valid":
            from packages.auth.identity import AuthenticationError

            raise AuthenticationError("invalid")
        return Principal(subject="alice", tenant_id=uuid4())


def test_health_is_public_and_schema_is_available():
    app = create_app(Settings(), verifier=FakeVerifier())
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/openapi.json").status_code == 200


def test_metrics_are_public_bounded_and_count_requests():
    app = create_app(Settings(otel_enabled=False), verifier=FakeVerifier())
    with TestClient(app) as client:
        client.get("/health/live")
        client.get("/does-not-exist")
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert (
            'platform_http_requests_total{method="GET",path="/health/live",status="200"} 1' in body
        )
        assert 'path="unmatched",status="404"' in body
        assert "tenant_id" not in body


def test_protected_context_rejects_missing_and_invalid_credentials():
    app = create_app(Settings(), verifier=FakeVerifier())
    with TestClient(app) as client:
        assert client.get("/v1/session").status_code == 401
        assert (
            client.get("/v1/session", headers={"Authorization": "Bearer invalid"}).status_code
            == 401
        )
        response = client.get(
            "/v1/session", headers={"Authorization": "Bearer valid", "X-Tenant-ID": str(uuid4())}
        )
        assert response.status_code == 200
        assert response.json()["subject"] == "alice"
        assert response.json()["tenant_id"] != response.request.headers["X-Tenant-ID"]


def test_readiness_fails_closed_without_database():
    app = create_app(Settings(database_url=None), verifier=FakeVerifier())
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 503


def test_unexpected_errors_do_not_expose_exception_details():
    app = create_app(Settings(), verifier=FakeVerifier())

    @app.get("/crash")
    async def crash():
        raise RuntimeError("super-secret")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")
        assert response.status_code == 500
        assert response.json() == {
            "error": {"code": "internal_error", "message": "Internal server error"}
        }
