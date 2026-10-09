"""Optional OpenTelemetry export; content and secrets never become span attributes."""

from contextlib import contextmanager
from opentelemetry import trace

_provider = None


def setup():
    global _provider
    from .config import settings

    if not settings().otel_enabled or _provider is not None:
        return
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    _provider = TracerProvider(resource=Resource.create({"service.name": "telegram-agent-control"}))
    _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(timeout=5)))
    trace.set_tracer_provider(_provider)


@contextmanager
def span(name, attributes=None):
    # Exception messages may contain upstream token URLs. Never auto-record them.
    with trace.get_tracer("tac").start_as_current_span(
        name, attributes=attributes or {}, record_exception=False, set_status_on_exception=False
    ) as current:
        yield current


def shutdown():
    if _provider:
        _provider.force_flush(timeout_millis=3000)
