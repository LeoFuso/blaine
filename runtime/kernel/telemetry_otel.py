"""Optional OpenTelemetry adapter for the neutral Recorder seam.

The kernel never imports this module. A deployment selects it, so an absent SDK
or an unavailable Collector degrades to NullRecorder instead of changing Task
behavior. No Grafana, Tempo, Loki, Langfuse or Phoenix concept appears here: the
only egress is OTLP, whose destination is deployment configuration.

Span names follow the OpenTelemetry GenAI convention `<operation> <target>`.
Content capture is off unless a deployment explicitly enables it, because
prompts, completions and tool payloads may carry secrets or repository contents.
"""
from contextlib import contextmanager
import os
import threading

from runtime.kernel.instrument import NullRecorder, SPAN_KINDS, span_name

SERVICE = 'blaine-runtime'
CONTENT_FLAG = 'BLAINE_TELEMETRY_CAPTURE_CONTENT'


class OtelRecorder:
    """Thin translation. It holds no batching, retry or transport policy itself."""
    def __init__(self, tracer, meter=None, capture_content=False):
        self.tracer = tracer
        self.capture_content = bool(capture_content)
        self.dropped_total = 0
        self._dropped = meter.create_counter('blaine.telemetry.dropped') if meter else None
        self._counters = {}
        self._meter = meter

    def _clean(self, attributes: dict) -> dict:
        if self.capture_content:
            return dict(attributes)
        return {k: v for k, v in attributes.items() if not k.endswith(('.content', '.messages', '.prompt',
                                                                       '.arguments', '.result'))}

    @contextmanager
    def span(self, name, *, kind, attributes):
        if kind not in SPAN_KINDS:
            raise ValueError('Unknown span kind')
        clean = self._clean(attributes)
        with self.tracer.start_as_current_span(name or span_name(kind, clean),
                                               attributes={'blaine.span.kind': kind, **clean}) as span:
            yield _Span(span)

    def event(self, name, *, attributes):
        """Point-in-time occurrence.

        Inside a span it is a span event. Outside one it becomes a zero-duration
        span, because this deployment exports traces only: an event attached to a
        non-recording span would be silently discarded, and losing a boundary
        observation is worse than representing it as an instantaneous span.
        """
        from opentelemetry import trace
        clean = self._clean(attributes)
        current = trace.get_current_span()
        if current.is_recording():
            current.add_event(name, attributes=clean)
            return
        with self.tracer.start_as_current_span(name, attributes={'blaine.event': True, **clean}):
            pass

    def count(self, name, value=1, attributes=None):
        if self._meter is None:
            return
        counter = self._counters.get(name) or self._meter.create_counter(name)
        self._counters[name] = counter
        counter.add(value, attributes or {})


class _Span:
    def __init__(self, span):
        self.span = span

    def set(self, **attributes):
        for key, value in attributes.items():
            self.span.set_attribute(key, value)

    def fail(self, reason):
        from opentelemetry.trace import Status, StatusCode
        self.span.set_status(Status(StatusCode.ERROR, reason))


def recorder(endpoint: str | None = None, *, service=SERVICE, capture_content=None,
             resource_attributes=None, timeout_ms=5000):
    """Return `(recorder, shutdown)`; `shutdown` flushes bounded buffered spans.

    An absent SDK yields NullRecorder, so a deployment without OpenTelemetry keeps
    exactly today's behavior. An unreachable Collector is not an error either: the
    batch processor drops spans in the background and execution continues.
    """
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        return NullRecorder(), lambda: None
    target = endpoint or os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT') or 'http://127.0.0.1:4318'
    provider = TracerProvider(resource=Resource.create({'service.name': service, **(resource_attributes or {})}))
    exporter = OTLPSpanExporter(endpoint=target.rstrip('/') + '/v1/traces', timeout=max(1, timeout_ms // 1000))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    if capture_content is None:
        capture_content = os.environ.get(CONTENT_FLAG) == 'true'

    def shutdown():
        # Shutdown with buffered telemetry is explicitly bounded. The exporter's
        # own retry loop can outlive the budget when the Collector is gone, so
        # the flush runs on a daemon thread and unexported spans are simply lost.
        # Telemetry loss is never a Task outcome, so nothing propagates here.
        def flush():
            try:
                provider.force_flush(timeout_ms)
                provider.shutdown()
            except Exception:
                pass
        worker = threading.Thread(target=flush, daemon=True, name='blaine-telemetry-shutdown')
        worker.start()
        worker.join(timeout_ms / 1000)
        return not worker.is_alive()
    return OtelRecorder(provider.get_tracer('blaine.kernel'), capture_content=capture_content), shutdown
