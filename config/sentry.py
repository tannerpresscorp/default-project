"""Sentry initialization for Django with secret and PII scrubbing.

Local to ``config/`` so the Django virtualenv does not depend on the platform
packages. The SDK stays inert unless ``SENTRY_DSN`` is set, query strings and
request bodies are never sent, and credential-bearing headers are overwritten
before export.
"""

import os
import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

_BEARER = re.compile(r"(?i)\bBearer\s+\S+")

_SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
        "x-api-key",
    }
)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_bearer(value)
    return value


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(
        marker in lowered
        for marker in ("authorization", "password", "secret", "api_key", "api-key", "token")
    )


def _redact_bearer(value: str) -> str:
    return _BEARER.sub("Bearer [REDACTED]", value)


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
            event[key] = _redact(value)
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        values = breadcrumbs.get("values")
        if isinstance(values, list):
            breadcrumbs["values"] = [_redact(value) for value in values]
    return event


def _sample_rate(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    rate = float(value)
    if not 0 <= rate <= 1:
        raise ValueError("SENTRY_TRACES_SAMPLE_RATE must be between 0 and 1")
    return rate


def init_sentry(dsn: str | None = None, **options: Any) -> bool:
    """Initialize Sentry when a DSN is available; otherwise do nothing."""
    dsn = dsn if dsn is not None else os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    if not dsn.startswith("https://"):
        raise ValueError("SENTRY_DSN must use https")
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "development"),
        traces_sample_rate=_sample_rate(os.environ.get("SENTRY_TRACES_SAMPLE_RATE")),
        send_default_pii=False,
        max_request_body_size="never",
        before_send=scrub_event,
        integrations=[DjangoIntegration()],
        **options,
    )
    return True
