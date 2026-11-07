import pytest

from packages.observability.metrics import InvalidMetric, Metrics


def test_metrics_render_sorted_bounded_labels_and_escape_values():
    metrics = Metrics()
    metrics.increment("platform_events_total", {"b": 'line\n"quoted"', "a": "first"})
    metrics.increment("platform_events_total", {"a": "first", "b": 'line\n"quoted"'})
    metrics.increment("platform_runs_total")

    rendered = metrics.render()

    assert 'platform_events_total{a="first",b="line\\n\\"quoted\\""} 2' in rendered
    assert "platform_runs_total 1" in rendered


def test_metrics_reject_invalid_names_and_negative_increments():
    metrics = Metrics()
    with pytest.raises(InvalidMetric):
        metrics.increment("Platform-Events")
    with pytest.raises(InvalidMetric):
        metrics.increment("platform_events_total", {"tenant-id": "x"})
    with pytest.raises(InvalidMetric):
        metrics.increment("platform_events_total", value=-1)


def test_metrics_drop_new_series_at_the_cardinality_bound():
    metrics = Metrics(max_series=2)
    metrics.increment("platform_events_total", {"label": "a"})
    metrics.increment("platform_events_total", {"label": "b"})
    metrics.increment("platform_events_total", {"label": "c"})
    metrics.increment("platform_events_total", {"label": "a"})

    rendered = metrics.render()
    assert 'label="a"} 2' in rendered
    assert 'label="b"} 1' in rendered
    assert 'label="c"' not in rendered
