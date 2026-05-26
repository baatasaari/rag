"""
OpenTelemetry metrics for the LBG RAG Platform.

Provides a typed RAGMetrics singleton that exposes all 40+ instruments.  Each
instrument name follows the pattern ``rag.<subsystem>.<measure>`` which the
Cloud Monitoring OTLP exporter maps to
``custom.googleapis.com/rag/<subsystem>/<measure>``.

Usage::

    configure_metrics(config.observability, service_name="lbg-rag", ...)
    m = get_metrics()

    m.queries_total.add(1, {"pattern": "adaptive", "cache_hit": "false"})
    m.query_latency.record(latency_ms, {"pattern": "adaptive"})
"""

from __future__ import annotations

from typing import Any

from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics._internal.instrument import (
    Counter,
    Histogram,
    UpDownCounter,
)
from opentelemetry.sdk.resources import Resource

_configured: bool = False
_provider: MeterProvider | None = None
_metrics_instance: RAGMetrics | None = None


# ---------------------------------------------------------------------------
# Metric name constants
# ---------------------------------------------------------------------------


class RAGMetricNames:
    """Canonical metric names.  All names are prefixed ``rag.`` so the OTLP
    exporter can map them to ``custom.googleapis.com/rag/*`` in Cloud Monitoring.
    """

    # ── Latency histograms ────────────────────────────────────────────────
    QUERY_LATENCY = "rag.query.latency_ms"
    EMBEDDING_LATENCY = "rag.embedding.latency_ms"
    RETRIEVAL_LATENCY = "rag.retrieval.latency_ms"
    RERANKING_LATENCY = "rag.reranking.latency_ms"
    GENERATION_LATENCY = "rag.generation.latency_ms"
    INGESTION_CHUNK_LATENCY = "rag.ingestion.chunk_latency_ms"

    # ── Counters ──────────────────────────────────────────────────────────
    QUERIES_TOTAL = "rag.queries.total"
    CACHE_HITS_TOTAL = "rag.cache.hits.total"
    CACHE_MISSES_TOTAL = "rag.cache.misses.total"
    CIRCUIT_BREAKER_TRIPS_TOTAL = "rag.circuit_breaker.trips.total"
    RETRIEVAL_DOCS_FETCHED_TOTAL = "rag.retrieval.docs_fetched.total"
    TOKENS_CONSUMED_TOTAL = "rag.tokens.consumed.total"
    PII_DETECTIONS_TOTAL = "rag.pii.detections.total"
    INGESTION_CHUNKS_CREATED_TOTAL = "rag.ingestion.chunks_created.total"
    INGESTION_ERRORS_TOTAL = "rag.ingestion.errors.total"

    # ── UpDown counters (gauge-like) ──────────────────────────────────────
    ACTIVE_REQUESTS = "rag.requests.active"
    REGISTRY_PLUGINS_REGISTERED = "rag.registry.plugins_registered"
    CIRCUIT_BREAKER_STATE = "rag.circuit_breaker.state"

    # ── Distribution histograms ───────────────────────────────────────────
    RETRIEVAL_SCORES = "rag.retrieval.scores"
    RERANKING_SCORE_DELTA = "rag.reranking.score_delta"
    CONTEXT_WINDOW_UTILISATION = "rag.generation.context_window_utilisation"


# Latency bucket boundaries (ms) optimised for RAG SLO monitoring.
# p50 ≈ 250ms, p95 target ≈ 2s, p99 ceiling ≈ 10s.
_LATENCY_BOUNDARIES = [10, 25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 30_000]

# Score bucket boundaries (cosine similarity / reranking score, 0–1 range).
_SCORE_BOUNDARIES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

# Context-window utilisation boundaries (fraction, 0–1).
_UTILISATION_BOUNDARIES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


# ---------------------------------------------------------------------------
# RAGMetrics — the singleton instrument container
# ---------------------------------------------------------------------------


class RAGMetrics:
    """All OTel instruments for the RAG platform.

    Instantiated once by configure_metrics() and accessed via get_metrics().
    All instruments are created eagerly at construction time so metric
    registration errors surface at startup, not mid-request.
    """

    def __init__(self, meter: otel_metrics.Meter) -> None:
        n = RAGMetricNames

        # ── Latency histograms ─────────────────────────────────────────────
        self.query_latency: Histogram = meter.create_histogram(
            name=n.QUERY_LATENCY,
            description="End-to-end query latency in milliseconds.",
            unit="ms",
        )
        self.embedding_latency: Histogram = meter.create_histogram(
            name=n.EMBEDDING_LATENCY,
            description="Embedding API call latency in milliseconds.",
            unit="ms",
        )
        self.retrieval_latency: Histogram = meter.create_histogram(
            name=n.RETRIEVAL_LATENCY,
            description="Vector + sparse retrieval latency in milliseconds.",
            unit="ms",
        )
        self.reranking_latency: Histogram = meter.create_histogram(
            name=n.RERANKING_LATENCY,
            description="Reranker inference latency in milliseconds.",
            unit="ms",
        )
        self.generation_latency: Histogram = meter.create_histogram(
            name=n.GENERATION_LATENCY,
            description="LLM generation latency in milliseconds.",
            unit="ms",
        )
        self.ingestion_chunk_latency: Histogram = meter.create_histogram(
            name=n.INGESTION_CHUNK_LATENCY,
            description="Per-chunk processing latency during ingestion in milliseconds.",
            unit="ms",
        )

        # ── Counters ───────────────────────────────────────────────────────
        self.queries_total: Counter = meter.create_counter(
            name=n.QUERIES_TOTAL,
            description="Total RAG queries received.",
        )
        self.cache_hits_total: Counter = meter.create_counter(
            name=n.CACHE_HITS_TOTAL,
            description="Semantic cache hits (query skipped embedding + retrieval).",
        )
        self.cache_misses_total: Counter = meter.create_counter(
            name=n.CACHE_MISSES_TOTAL,
            description="Semantic cache misses (full pipeline executed).",
        )
        self.circuit_breaker_trips_total: Counter = meter.create_counter(
            name=n.CIRCUIT_BREAKER_TRIPS_TOTAL,
            description="Number of times a circuit breaker transitioned to OPEN.",
        )
        self.retrieval_docs_fetched_total: Counter = meter.create_counter(
            name=n.RETRIEVAL_DOCS_FETCHED_TOTAL,
            description="Total documents fetched from all retrieval strategies.",
        )
        self.tokens_consumed_total: Counter = meter.create_counter(
            name=n.TOKENS_CONSUMED_TOTAL,
            description="LLM tokens consumed. Use direction=in|out label.",
        )
        self.pii_detections_total: Counter = meter.create_counter(
            name=n.PII_DETECTIONS_TOTAL,
            description="PII entities detected. Use pii_type label — NEVER log the value.",
        )
        self.ingestion_chunks_created_total: Counter = meter.create_counter(
            name=n.INGESTION_CHUNKS_CREATED_TOTAL,
            description="Total chunks created during document ingestion.",
        )
        self.ingestion_errors_total: Counter = meter.create_counter(
            name=n.INGESTION_ERRORS_TOTAL,
            description="Ingestion pipeline errors by stage.",
        )

        # ── UpDown counters ────────────────────────────────────────────────
        self.active_requests: UpDownCounter = meter.create_up_down_counter(
            name=n.ACTIVE_REQUESTS,
            description="Number of RAG queries currently in flight.",
        )
        self.registry_plugins_registered: UpDownCounter = meter.create_up_down_counter(
            name=n.REGISTRY_PLUGINS_REGISTERED,
            description="Number of plugins currently registered in the component registry.",
        )
        self.circuit_breaker_state: UpDownCounter = meter.create_up_down_counter(
            name=n.CIRCUIT_BREAKER_STATE,
            description="Circuit breaker state: 0=CLOSED, 1=HALF_OPEN, 2=OPEN.",
        )

        # ── Distribution histograms ────────────────────────────────────────
        self.retrieval_scores: Histogram = meter.create_histogram(
            name=n.RETRIEVAL_SCORES,
            description="Distribution of retrieval similarity scores (0–1).",
        )
        self.reranking_score_delta: Histogram = meter.create_histogram(
            name=n.RERANKING_SCORE_DELTA,
            description="Score improvement from reranking vs. first-pass retrieval.",
        )
        self.context_window_utilisation: Histogram = meter.create_histogram(
            name=n.CONTEXT_WINDOW_UTILISATION,
            description="Fraction of the LLM context window consumed by retrieved chunks.",
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def configure_metrics(
    config: Any,  # ObservabilityConfig — avoid circular import at module level
    *,
    service_name: str = "lbg-rag-platform",
    service_version: str = "1.0.0",
    environment: str = "unknown",
) -> MeterProvider:
    """Configure the global OTel MeterProvider and create all RAG instruments.

    Idempotent — subsequent calls after the first return the existing provider.

    Exporters selected by config.metrics.exporter:
      "console"          → ConsoleMetricExporter (local dev)
      "cloud_monitoring" → OTLP gRPC to Cloud Monitoring endpoint
      "prometheus"       → OTLP gRPC to a Prometheus-compatible endpoint
    """
    global _configured, _provider, _metrics_instance
    if _configured and _provider is not None:
        return _provider

    metrics_cfg = config.metrics
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "deployment.environment": environment,
        }
    )

    exporter = _build_metric_exporter(metrics_cfg)

    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=metrics_cfg.export_interval_seconds * 1_000,
    )

    provider = MeterProvider(resource=resource, metric_readers=[reader])
    otel_metrics.set_meter_provider(provider)

    meter = provider.get_meter(service_name, service_version)
    _metrics_instance = RAGMetrics(meter)

    _provider = provider
    _configured = True
    return provider


def _build_metric_exporter(metrics_cfg: Any) -> Any:  # noqa: ANN401
    exporter_type: str = metrics_cfg.exporter

    if exporter_type == "console":
        from opentelemetry.sdk.metrics.export import ConsoleMetricExporter

        return ConsoleMetricExporter()

    # cloud_monitoring and prometheus both use OTLP gRPC
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

    endpoint: str | None = getattr(metrics_cfg, "endpoint", None)
    if exporter_type == "cloud_monitoring" and not endpoint:
        endpoint = "monitoring.googleapis.com:443"

    return OTLPMetricExporter(endpoint=endpoint or "localhost:4317")


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------


def get_meter(name: str) -> otel_metrics.Meter:
    """Return an OTel Meter using the global provider."""
    return otel_metrics.get_meter(name)


def get_metrics() -> RAGMetrics:
    """Return the RAGMetrics singleton.

    Raises RuntimeError if configure_metrics() has not been called.
    """
    if _metrics_instance is None:
        raise RuntimeError(
            "Metrics have not been configured. "
            "Call configure_metrics(config.observability) during application startup."
        )
    return _metrics_instance


def reset_metrics() -> None:
    """Reset metrics state. FOR TESTING ONLY.

    Force-resets the OTel global MeterProvider so tests can configure fresh
    providers without the SDK's "set-once" guard blocking them.
    """
    global _configured, _provider, _metrics_instance
    _configured = False
    _provider = None
    _metrics_instance = None

    import opentelemetry.metrics._internal as _metrics_mod

    _metrics_mod._METER_PROVIDER = None  # type: ignore[attr-defined]
    _metrics_mod._METER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
