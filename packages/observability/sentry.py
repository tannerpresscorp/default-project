"""Sentry initialization with secret and PII scrubbing.

The SDK is inert unless a DSN is configured, so tests and local runs need no
Sentry account. Query strings and request bodies are never sent, and headers
that commonly carry credentials are overwritten before export.
"""

from typing import Any, cast

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from packages.config.settings import Settings
from packages.observability.logging import redact

_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
        "x-api-key",
    }
)


def scrub_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                key: "[REDACTED]" if key.lower() in _SENSITIVE_HEADERS else value
                for key, value in headers.items()
            }
        for key in ("cookies", "data", "query_string"):
            request.pop(key, None)
    for key in ("contexts", "extra", "tags"):
        value = event.get(key)
        if isinstance(value, dict):
            event[key] = redact(value)
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        values = breadcrumbs.get("values")
        if isinstance(values, list):
            breadcrumbs["values"] = [redact(value) for value in values]
    return event


def init_sentry(settings: Settings, **options: Any) -> bool:
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        max_request_body_size="never",
        before_send=cast(Any, scrub_event),
        integrations=[StarletteIntegration(), FastApiIntegration()],
        **options,
    )
    return True


def capture_exception(error: BaseException) -> None:
    """Report an exception handled by application code before it is swallowed."""
    sentry_sdk.capture_exception(error)
