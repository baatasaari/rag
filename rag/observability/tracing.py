"""
OpenTelemetry tracing for the LBG RAG Platform.

Provides:
  - configure_tracing(config)  — sets global OTel TracerProvider once at startup
  - get_tracer(name)           — returns a Tracer for the given module
  - record_span(name, **attrs) — context manager wrapping every RAG operation
  - record_exception(span, exc)— structured exception capture on an active span
  - RAGAttributes              — canonical span attribute key constants
  - TailSamplingSpanProcessor  — force-exports error / slow spans regardless of
                                 head sampling decision (bank-grade auditability)

Usage:
    configure_tracing(config.observability, service_name="lbg-rag", ...)

    with record_span("embedding.embed_query", **{RAGAttributes.MODEL: "text-embedding-004"}):
        vectors = await embed(text)
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generator, Iterator

from opentelemetry import trace as otel_trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ParentBased,
    TraceIdRatioBased,
)
from opentelemetry.trace import NonRecordingSpan, StatusCode
from opentelemetry.trace.span import SpanContext

_configured: bool = False
_provider: TracerProvider | None = None


# ---------------------------------------------------------------------------
# Attribute key constants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RAGAttributes:
    """Canonical OTel span attribute keys for all RAG operations.

    Every span produced by the platform MUST use these constants to guarantee
    consistent attribute names across Cloud Trace dashboards and alerts.
    """

    # Query context
    QUERY_ID: str = "rag.query_id"
    PATTERN: str = "rag.pattern"
    SESSION_ID: str = "rag.session_id"

    # Embedding
    MODEL: str = "rag.model"
    PROVIDER: str = "rag.provider"
    EMBEDDING_TASK_TYPE: str = "rag.embedding.task_type"
    EMBEDDING_DIMENSIONS: str = "rag.embedding.dimensions"

    # Retrieval
    RETRIEVAL_STRATEGY: str = "rag.retrieval.strategy"
    RETRIEVAL_TOP_K: str = "rag.retrieval.top_k"
    RETRIEVAL_CHUNK_COUNT: str = "rag.retrieval.chunk_count"
    RETRIEVAL_SCORE_MAX: str = "rag.retrieval.score_max"
    RETRIEVAL_SCORE_MIN: str = "rag.retrieval.score_min"
    CACHE_HIT: str = "rag.cache_hit"

    # Generation
    TOKENS_IN: str = "rag.tokens.input"
    TOKENS_OUT: str = "rag.tokens.output"
    STOP_REASON: str = "rag.generation.stop_reason"
    CITATION_COUNT: str = "rag.generation.citation_count"

    # Chunking / ingestion
    CHUNK_COUNT: str = "rag.chunk_count"
    SOURCE_URI: str = "rag.source_uri"
    INGESTION_STAGE: str = "rag.ingestion.stage"

    # Reranking
    RERANKER_MODEL: str = "rag.reranker.model"
    RERANKER_TOP_N: str = "rag.reranker.top_n"

    # Performance (set by record_span on exit)
    LATENCY_MS: str = "rag.latency_ms"

    # Error
    ERROR_TYPE: str = "rag.error.type"
    ERROR_COMPONENT: str = "rag.error.component"


# Singleton instance so callers can do `RAGAttributes.QUERY_ID` without
# instantiating. Because the class is frozen the values never change.
RAGAttributes = RAGAttributes()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tail-sampling span processor
# ---------------------------------------------------------------------------


class TailSamplingSpanProcessor:
    """Force-export spans that end with ERROR status or exceed the slow threshold.

    Head-sampling (TraceIdRatioBased) may have marked such a span RECORD_ONLY
    (not sampled).  on_end() is still called for RECORD_ONLY spans, giving us
    the chance to export them via a dedicated always-on exporter.

    Cloud Trace deduplicates by (trace_id, span_id), so double-exports from
    spans that were both sampled AND rescued are safe.
    """

    def __init__(
        self,
        exporter: SpanExporter,
        *,
        always_sample_errors: bool,
        always_sample_slow_ms: int,
    ) -> None:
        self._exporter = exporter
        self._always_sample_errors = always_sample_errors
        self._always_sample_slow_ms = always_sample_slow_ms

    def on_start(self, span: Span, parent_context: Any = None) -> None:  # noqa: ANN401
        pass

    def on_end(self, span: ReadableSpan) -> None:
        if span.context is None or not span.context.is_valid:
            return
        # Skip spans already included in the sampled trace — the BatchSpanProcessor
        # handles those.
        if span.context.trace_flags.sampled:
            return

        should_rescue = False
        if self._always_sample_errors and span.status.status_code == StatusCode.ERROR:
            should_rescue = True
        elif self._always_sample_slow_ms > 0:
            latency = (span.attributes or {}).get(RAGAttributes.LATENCY_MS, 0)
            if isinstance(latency, (int, float)) and latency > self._always_sample_slow_ms:
                should_rescue = True

        if should_rescue:
            self._exporter.export([span])  # type: ignore[arg-type]

    def shutdown(self) -> None:
        self._exporter.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_tracing(
    config: Any,  # ObservabilityConfig — avoid circular import at module level
    *,
    service_name: str = "lbg-rag-platform",
    service_version: str = "1.0.0",
    environment: str = "unknown",
) -> TracerProvider:
    """Configure the global OTel TracerProvider.

    Idempotent — subsequent calls after the first return the existing provider.

    Exporters selected by config.tracing.exporter:
      "console"     → ConsoleSpanExporter (local dev)
      "cloud_trace" → OTLP gRPC to Cloud Trace endpoint
      "otlp"        → OTLP gRPC to config.tracing.endpoint
    """
    global _configured, _provider
    if _configured and _provider is not None:
        return _provider

    trace_cfg = config.tracing

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": environment,
        }
    )

    # Sampler: always-on in dev (sampling_rate=1.0 in development overlay),
    # ratio-based in staging/prod, wrapped in ParentBased so downstream
    # services respect the upstream sampling decision.
    if trace_cfg.sampling_rate >= 1.0:
        sampler = ALWAYS_ON
    else:
        sampler = ParentBased(root=TraceIdRatioBased(trace_cfg.sampling_rate))

    provider = TracerProvider(resource=resource, sampler=sampler)

    # Primary exporter
    primary_exporter = _build_span_exporter(trace_cfg)
    provider.add_span_processor(BatchSpanProcessor(primary_exporter))

    # Tail-sampling processor: rescues error/slow spans even when head-sampled out
    if trace_cfg.always_sample_errors or trace_cfg.always_sample_slow_requests_ms:
        rescue_exporter = _build_span_exporter(trace_cfg)
        provider.add_span_processor(
            TailSamplingSpanProcessor(  # type: ignore[arg-type]
                rescue_exporter,
                always_sample_errors=trace_cfg.always_sample_errors,
                always_sample_slow_ms=trace_cfg.always_sample_slow_requests_ms,
            )
        )

    otel_trace.set_tracer_provider(provider)
    _provider = provider
    _configured = True
    return provider


def _build_span_exporter(trace_cfg: Any) -> SpanExporter:  # noqa: ANN401
    exporter_type: str = trace_cfg.exporter

    if exporter_type == "console":
        return ConsoleSpanExporter()

    # Both "cloud_trace" and "otlp" use the OTLP gRPC exporter.
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    endpoint = trace_cfg.endpoint
    if exporter_type == "cloud_trace" and not endpoint:
        # Cloud Trace OTLP gRPC endpoint (requires ADC / Workload Identity)
        endpoint = "cloudtrace.googleapis.com:443"

    return OTLPSpanExporter(endpoint=endpoint or "localhost:4317")


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------


def get_tracer(name: str) -> otel_trace.Tracer:
    """Return an OTel Tracer.  Uses the global provider set by configure_tracing()."""
    return otel_trace.get_tracer(name)


def record_exception(span: otel_trace.Span, exc: Exception) -> None:
    """Record exc on span, set ERROR status, and preserve the original exception."""
    span.record_exception(exc)
    span.set_status(
        otel_trace.Status(
            status_code=StatusCode.ERROR,
            description=f"{type(exc).__name__}: {exc}",
        )
    )
    span.set_attribute(RAGAttributes.ERROR_TYPE, type(exc).__name__)


@contextmanager
def record_span(
    name: str,
    *,
    tracer_name: str = "rag",
    **attributes: Any,
) -> Generator[otel_trace.Span, None, None]:
    """Sync context manager that wraps a RAG operation in an OTel span.

    Works correctly in both synchronous and async call sites (a sync context
    manager used inside `async def` does not require `async with`).

    Records latency_ms automatically on exit.  Re-raises all exceptions after
    marking the span as ERROR and recording the exception event.

    Example::

        with record_span("retrieval.hybrid_search", **{
            RAGAttributes.RETRIEVAL_STRATEGY: "hybrid",
            RAGAttributes.RETRIEVAL_TOP_K: 10,
        }) as span:
            results = await vector_store.search(...)
            span.set_attribute(RAGAttributes.RETRIEVAL_CHUNK_COUNT, len(results))
    """
    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)

        start = time.monotonic()
        try:
            yield span
        except Exception as exc:
            record_exception(span, exc)
            raise
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            span.set_attribute(RAGAttributes.LATENCY_MS, round(latency_ms, 2))


def reset_tracing() -> None:
    """Reset tracing state. FOR TESTING ONLY.

    Force-resets the OTel global TracerProvider so tests can configure fresh
    providers without the SDK's "set-once" guard blocking them.
    """
    global _configured, _provider
    _configured = False
    _provider = None

    import opentelemetry.trace as _trace_mod

    _trace_mod._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    _trace_mod._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
