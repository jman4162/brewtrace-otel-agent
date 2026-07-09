"""OpenTelemetry wiring for BrewTrace.

The only module that touches the OTel SDK directly. Strands handles its own
spans (agent loop, model calls, tool executions) via StrandsTelemetry; this
module adds the manual `brewtrace.request` parent span carrying the parsed
brew attributes.

Naming note: custom attributes live in our own `brew.*` / `taste.*` / `eval.*`
namespaces. OTel guidance says never to extend reserved namespaces like
`gen_ai.*` — a future spec revision could claim the name and collide.

Semconv note: as of strands-agents 1.46 the auto-emitted spans use the legacy
GenAI attribute names (`gen_ai.system`, `gen_ai.usage.prompt_tokens`). The
current experimental spec renamed these (`gen_ai.provider.name`,
`gen_ai.usage.input_tokens`); set OTEL_SEMCONV_STABILITY_OPT_IN to opt in to
newer names. Dashboards should query both generations.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace

from brewtrace.models import BrewLog

DEFAULT_OTLP_ENDPOINT = "http://localhost:4318"

_configured = False


def setup_telemetry(*, otlp: bool = True, console: bool = False, metrics: bool = False) -> None:
    """Configure the global tracer/meter providers via StrandsTelemetry.

    Safe to call once per process; later calls are no-ops.
    """
    global _configured
    if _configured:
        return

    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    os.environ.setdefault("OTEL_SERVICE_NAME", "brewtrace")

    from strands.telemetry import StrandsTelemetry

    strands_telemetry = StrandsTelemetry()
    if otlp:
        strands_telemetry.setup_otlp_exporter()
    if console:
        strands_telemetry.setup_console_exporter()
    if metrics:
        strands_telemetry.setup_meter(enable_otlp_exporter=True)
    _configured = True


@contextmanager
def brew_request_span(brew: BrewLog, extra: dict | None = None) -> Iterator[trace.Span]:
    """Parent span for one diagnosis request, carrying the parsed brew data.

    Strands' agent spans nest under this automatically because both use the
    global TracerProvider. Attributes come from the deterministic parse, which
    is why the parser runs even in agent mode.
    """
    tracer = trace.get_tracer("brewtrace")
    with tracer.start_as_current_span("brewtrace.request") as span:
        attributes: dict[str, str | float | int] = {}
        if brew.method:
            attributes["brew.method"] = brew.method.value
        if brew.dose_g is not None:
            attributes["brew.dose_g"] = brew.dose_g
        if brew.water_g is not None:
            attributes["brew.water_g"] = brew.water_g
        if brew.ratio is not None:
            attributes["brew.ratio"] = brew.ratio
        if brew.temperature_c is not None:
            attributes["brew.temperature_c"] = brew.temperature_c
        if brew.drawdown_s is not None:
            attributes["brew.drawdown_seconds"] = brew.drawdown_s
        if brew.grind_setting:
            attributes["brew.grind_setting"] = brew.grind_setting
        if brew.defect:
            attributes["taste.primary_defect"] = brew.defect.value
        for key, value in (extra or {}).items():
            attributes[key] = value
        span.set_attributes(attributes)
        yield span
