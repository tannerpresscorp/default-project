"""Minimal in-process Prometheus text metrics with bounded labels.

This is a foundation, not a metrics pipeline. Counters live in one process and
are reset on restart; aggregation, persistence and scraping belong to an
external collector. Labels must stay bounded and must never contain tenant,
run, conversation or invocation identifiers.
"""

import re
from collections import Counter
from collections.abc import Mapping
from threading import Lock

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_SERIES = 500


class InvalidMetric(ValueError):
    """The metric name or label set is not valid for bounded exposition."""


class Metrics:
    """Thread-safe counters rendered in the Prometheus text format."""

    def __init__(self, *, max_series: int = _MAX_SERIES) -> None:
        if max_series < 1:
            raise ValueError("max_series must be positive")
        self._max_series = max_series
        self._counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
        self._lock = Lock()

    def increment(
        self,
        name: str,
        labels: Mapping[str, str] | None = None,
        *,
        value: int = 1,
    ) -> None:
        if not _NAME.fullmatch(name):
            raise InvalidMetric(f"invalid metric name: {name!r}")
        if value < 0:
            raise InvalidMetric("counter increments must not be negative")
        rendered = tuple(sorted((labels or {}).items()))
        for label, _ in rendered:
            if not _LABEL.fullmatch(label):
                raise InvalidMetric(f"invalid label name: {label!r}")
        key = (name, rendered)
        with self._lock:
            if key not in self._counters and len(self._counters) >= self._max_series:
                return
            self._counters[key] += value

    def value(self, name: str, labels: Mapping[str, str] | None = None) -> int:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            return self._counters.get(key, 0)

    def render(self) -> str:
        with self._lock:
            snapshot = sorted(self._counters.items())
        lines = []
        for (name, labels), value in snapshot:
            if labels:
                label_text = ",".join(
                    f'{label}="{_escape(value_text)}"' for label, value_text in labels
                )
                lines.append(f"{name}{{{label_text}}} {value}")
            else:
                lines.append(f"{name} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
