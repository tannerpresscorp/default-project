from packages.observability.logging import redact


def test_recursive_redaction_does_not_mutate_input():
    value = {
        "Authorization": "Bearer abc",
        "nested": [{"password": "hunter2", "safe": "hello"}],
        "api_key": "secret",
    }
    result = redact(value)
    assert result == {
        "Authorization": "[REDACTED]",
        "nested": [{"password": "[REDACTED]", "safe": "hello"}],
        "api_key": "[REDACTED]",
    }
    assert value["Authorization"] == "Bearer abc"


def test_http_tracing_does_not_capture_auth_header(monkeypatch):
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from apps.api.main import create_app
    from packages.config.settings import Settings

    monkeypatch.setenv("OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST", ".*")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = create_app(Settings(), tracer_provider=provider)
    with TestClient(app) as client:
        client.get(
            "/v1/session?api_key=secret-in-query",
            headers={"Authorization": "Bearer super-secret"},
        )
    spans = exporter.get_finished_spans()
    assert spans
    assert "super-secret" not in repr([span.attributes for span in spans])
    assert "secret-in-query" not in repr([span.attributes for span in spans])


def test_unhandled_exception_does_not_leak_into_exported_traces():
    from fastapi.testclient import TestClient
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from apps.api.main import create_app
    from packages.config.settings import Settings

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = create_app(Settings(), tracer_provider=provider)

    @app.get("/crash")
    async def crash():
        raise RuntimeError("secret-in-exception")

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/crash").status_code == 500
    spans = exporter.get_finished_spans()
    assert spans
    telemetry = [
        (
            span.attributes,
            span.status.description,
            [(event.name, event.attributes) for event in span.events],
        )
        for span in spans
    ]
    assert "secret-in-exception" not in repr(telemetry)
