import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_SENSITIVE = re.compile(r"authorization|password|secret|api.?key|token|credential", re.IGNORECASE)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")


def redact(value: Any, pii_keys: frozenset[str] = frozenset()) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if _SENSITIVE.search(str(key)) or str(key).lower() in pii_keys
            else redact(item, pii_keys)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item, pii_keys) for item in value]
    if isinstance(value, str):
        return _BEARER.sub("Bearer [REDACTED]", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload["fields"] = fields
        return json.dumps(redact(payload), default=str)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("platform")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
