import pytest
from pydantic import ValidationError

from packages.config.settings import Settings
from packages.observability.sentry import capture_exception, init_sentry, scrub_event

_DSN = "https://public@o1.ingest.sentry.io/42"


def test_init_is_inert_without_dsn(monkeypatch):
    calls = []
    monkeypatch.setattr("sentry_sdk.init", lambda **kwargs: calls.append(kwargs))

    assert init_sentry(Settings()) is False
    assert calls == []


def test_init_uses_safe_options(monkeypatch):
    calls = []
    monkeypatch.setattr("sentry_sdk.init", lambda **kwargs: calls.append(kwargs))

    settings = Settings(sentry_dsn=_DSN, sentry_environment="test", sentry_traces_sample_rate=0.5)
    assert init_sentry(settings) is True

    (options,) = calls
    assert options["dsn"] == _DSN
    assert options["environment"] == "test"
    assert options["traces_sample_rate"] == 0.5
    assert options["send_default_pii"] is False
    assert options["max_request_body_size"] == "never"
    assert options["before_send"] is scrub_event
    assert {type(integration).__name__ for integration in options["integrations"]} == {
        "StarletteIntegration",
        "FastApiIntegration",
    }


def test_scrub_event_removes_credentials_and_payloads():
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer super-secret",
                "Cookie": "session=super-secret",
                "X-Api-Key": "super-secret",
                "Accept": "application/json",
            },
            "cookies": {"session": "super-secret"},
            "data": {"password": "super-secret"},
            "query_string": "api_key=super-secret",
        },
        "contexts": {"request": {"token": "super-secret", "safe": "hello"}},
        "extra": {"password": "super-secret", "safe": "hello"},
        "tags": {"api-key": "super-secret"},
        "breadcrumbs": {
            "values": [
                {"message": "Authorization: Bearer super-secret"},
                {"data": {"secret": "super-secret", "safe": "hello"}},
            ]
        },
    }

    scrubbed = scrub_event(event, {})

    assert "super-secret" not in repr(scrubbed)
    request = scrubbed["request"]
    assert request["headers"]["Authorization"] == "[REDACTED]"
    assert request["headers"]["Cookie"] == "[REDACTED]"
    assert request["headers"]["X-Api-Key"] == "[REDACTED]"
    assert request["headers"]["Accept"] == "application/json"
    assert "cookies" not in request
    assert "data" not in request
    assert "query_string" not in request
    assert scrubbed["extra"] == {"password": "[REDACTED]", "safe": "hello"}
    assert scrubbed["contexts"]["request"] == {"token": "[REDACTED]", "safe": "hello"}
    assert scrubbed["tags"] == {"api-key": "[REDACTED]"}
    assert scrubbed["breadcrumbs"]["values"] == [
        {"message": "Authorization: Bearer [REDACTED]"},
        {"data": {"secret": "[REDACTED]", "safe": "hello"}},
    ]


def test_scrub_event_tolerates_missing_request():
    assert scrub_event({"message": "boom"}, {}) == {"message": "boom"}


def test_capture_exception_delegates(monkeypatch):
    captured = []
    monkeypatch.setattr("sentry_sdk.capture_exception", captured.append)
    error = RuntimeError("boom")

    capture_exception(error)

    assert captured == [error]


def test_handled_unexpected_error_is_reported(monkeypatch):
    from fastapi.testclient import TestClient

    from apps.api.main import create_app

    reported = []
    monkeypatch.setattr("apps.api.main.capture_exception", reported.append)
    app = create_app(Settings(otel_enabled=False))

    @app.get("/crash")
    async def crash():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/crash").status_code == 500

    assert len(reported) == 1
    assert isinstance(reported[0], RuntimeError)


@pytest.mark.parametrize("dsn", ["http://public@o1.ingest.sentry.io/42", "sentry.io/42"])
def test_dsn_must_use_https(dsn):
    with pytest.raises(ValidationError):
        Settings(sentry_dsn=dsn)


@pytest.mark.parametrize("rate", [-0.1, 1.1])
def test_sample_rate_must_be_a_fraction(rate):
    with pytest.raises(ValidationError):
        Settings(sentry_traces_sample_rate=rate)
