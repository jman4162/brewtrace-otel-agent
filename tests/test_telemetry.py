"""Telemetry tests using an in-memory exporter — no collector needed."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from brewtrace.models import parse_brew_log
from brewtrace.telemetry import brew_request_span, record_recommendation


def _capture_span(brew, extra=None):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # brew_request_span uses the global tracer; give it this provider's tracer
    # by patching trace.get_tracer's provider argument path via the provider.
    tracer = provider.get_tracer("brewtrace-test")
    original = trace.get_tracer
    trace.get_tracer = lambda *a, **k: tracer  # type: ignore[assignment]
    try:
        with brew_request_span(brew, extra=extra):
            pass
    finally:
        trace.get_tracer = original
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    return spans[0]


def test_brew_attributes_set():
    brew = parse_brew_log("16g/250g V60, 94C, 3:45 drawdown, sour and thin")
    span = _capture_span(brew)
    attrs = dict(span.attributes)
    assert span.name == "brewtrace.request"
    assert attrs["brew.method"] == "v60"
    assert attrs["brew.dose_g"] == 16
    assert attrs["brew.water_g"] == 250
    assert attrs["brew.ratio"] == 15.62
    assert attrs["brew.temperature_c"] == 94
    assert attrs["brew.drawdown_seconds"] == 225
    assert attrs["taste.primary_defect"] == "sour_thin"


def test_missing_fields_omitted():
    brew = parse_brew_log("v60 tastes sour")
    attrs = dict(_capture_span(brew).attributes)
    assert "brew.dose_g" not in attrs
    assert "brew.temperature_c" not in attrs
    assert attrs["taste.primary_defect"] == "sour"


def test_extra_attributes_merged():
    brew = parse_brew_log("16g/250g v60, sour")
    attrs = dict(
        _capture_span(brew, extra={"eval.case_id": "x", "brew.source": "beanbench"}).attributes
    )
    assert attrs["eval.case_id"] == "x"
    assert attrs["brew.source"] == "beanbench"


def test_record_recommendation_safe_without_meter():
    # No MeterProvider configured: the API no-op must absorb this quietly.
    record_recommendation("grind", 1.23)
    record_recommendation("temperature", 0.5)
