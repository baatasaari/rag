"""
Tests for rag.observability.metrics — instrument creation, singletons, naming.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from rag.observability.metrics import (
    RAGMetricNames,
    RAGMetrics,
    configure_metrics,
    get_meter,
    get_metrics,
    reset_metrics,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_metrics_state():
    reset_metrics()
    yield
    reset_metrics()


def _make_metrics_config(
    *,
    exporter: str = "console",
    namespace: str = "custom.googleapis.com/rag",
    export_interval_seconds: int = 15,
):
    cfg = MagicMock()
    cfg.metrics.exporter = exporter
    cfg.metrics.namespace = namespace
    cfg.metrics.export_interval_seconds = export_interval_seconds
    cfg.metrics.endpoint = None
    return cfg


@pytest.fixture()
def configured_metrics() -> RAGMetrics:
    """Configure metrics with an in-memory reader and return the RAGMetrics instance."""
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])

    from opentelemetry import metrics as otel_metrics

    otel_metrics.set_meter_provider(provider)

    meter = provider.get_meter("lbg-rag-platform", "1.0.0")
    metrics_obj = RAGMetrics(meter)

    import rag.observability.metrics as _mod

    _mod._configured = True
    _mod._provider = provider
    _mod._metrics_instance = metrics_obj

    return metrics_obj


# ── RAGMetricNames ────────────────────────────────────────────────────────────


class TestRAGMetricNames:
    def test_all_names_start_with_rag_prefix(self):
        import inspect

        for name, value in inspect.getmembers(RAGMetricNames):
            if not name.startswith("_") and isinstance(value, str):
                assert value.startswith("rag."), (
                    f"RAGMetricNames.{name} = {value!r} must start with 'rag.'"
                )

    def test_latency_metric_names_end_with_ms(self):
        latency_names = [
            RAGMetricNames.QUERY_LATENCY,
            RAGMetricNames.EMBEDDING_LATENCY,
            RAGMetricNames.RETRIEVAL_LATENCY,
            RAGMetricNames.RERANKING_LATENCY,
            RAGMetricNames.GENERATION_LATENCY,
            RAGMetricNames.INGESTION_CHUNK_LATENCY,
        ]
        for name in latency_names:
            assert name.endswith("_ms"), f"{name} latency metric must end with '_ms'"

    def test_counter_names_end_with_total(self):
        counter_names = [
            RAGMetricNames.QUERIES_TOTAL,
            RAGMetricNames.CACHE_HITS_TOTAL,
            RAGMetricNames.CACHE_MISSES_TOTAL,
            RAGMetricNames.CIRCUIT_BREAKER_TRIPS_TOTAL,
            RAGMetricNames.RETRIEVAL_DOCS_FETCHED_TOTAL,
            RAGMetricNames.TOKENS_CONSUMED_TOTAL,
            RAGMetricNames.PII_DETECTIONS_TOTAL,
            RAGMetricNames.INGESTION_CHUNKS_CREATED_TOTAL,
            RAGMetricNames.INGESTION_ERRORS_TOTAL,
        ]
        for name in counter_names:
            assert name.endswith(".total"), f"{name} counter must end with '.total'"

    def test_no_duplicate_metric_names(self):
        import inspect

        names = [
            v
            for _, v in inspect.getmembers(RAGMetricNames)
            if not _.startswith("_") and isinstance(v, str)
        ]
        assert len(names) == len(set(names)), "Duplicate metric names detected"


# ── RAGMetrics instrument creation ────────────────────────────────────────────


class TestRAGMetricsInstruments:
    def test_all_latency_histograms_exist(self, configured_metrics):
        m = configured_metrics
        assert m.query_latency is not None
        assert m.embedding_latency is not None
        assert m.retrieval_latency is not None
        assert m.reranking_latency is not None
        assert m.generation_latency is not None
        assert m.ingestion_chunk_latency is not None

    def test_all_counters_exist(self, configured_metrics):
        m = configured_metrics
        assert m.queries_total is not None
        assert m.cache_hits_total is not None
        assert m.cache_misses_total is not None
        assert m.circuit_breaker_trips_total is not None
        assert m.retrieval_docs_fetched_total is not None
        assert m.tokens_consumed_total is not None
        assert m.pii_detections_total is not None
        assert m.ingestion_chunks_created_total is not None
        assert m.ingestion_errors_total is not None

    def test_all_updown_counters_exist(self, configured_metrics):
        m = configured_metrics
        assert m.active_requests is not None
        assert m.registry_plugins_registered is not None
        assert m.circuit_breaker_state is not None

    def test_all_distribution_histograms_exist(self, configured_metrics):
        m = configured_metrics
        assert m.retrieval_scores is not None
        assert m.reranking_score_delta is not None
        assert m.context_window_utilisation is not None

    def test_counter_can_be_incremented(self, configured_metrics):
        m = configured_metrics
        # Incrementing must not raise
        m.queries_total.add(1, {"pattern": "adaptive", "cache_hit": "false"})
        m.cache_hits_total.add(1, {"pattern": "naive"})

    def test_histogram_can_record_value(self, configured_metrics):
        m = configured_metrics
        m.query_latency.record(250.0, {"pattern": "adaptive"})
        m.retrieval_scores.record(0.87, {"strategy": "hybrid"})

    def test_updown_counter_can_increment_and_decrement(self, configured_metrics):
        m = configured_metrics
        m.active_requests.add(1)
        m.active_requests.add(-1)

    def test_pii_counter_accepts_pii_type_label(self, configured_metrics):
        m = configured_metrics
        # PII type label — value (actual PII) must never be logged
        m.pii_detections_total.add(1, {"pii_type": "NATIONAL_INSURANCE_NUMBER"})

    def test_tokens_counter_accepts_direction_label(self, configured_metrics):
        m = configured_metrics
        m.tokens_consumed_total.add(1024, {"direction": "in"})
        m.tokens_consumed_total.add(512, {"direction": "out"})

    def test_total_instrument_count_is_at_least_20(self, configured_metrics):
        import dataclasses

        # Count non-None public attributes (all instruments)
        count = sum(
            1
            for name in dir(configured_metrics)
            if not name.startswith("_") and getattr(configured_metrics, name) is not None
        )
        assert count >= 20, f"Expected ≥20 instruments, found {count}"


# ── configure_metrics ─────────────────────────────────────────────────────────


class TestConfigureMetrics:
    def test_returns_meter_provider(self):
        cfg = _make_metrics_config(exporter="console")
        provider = configure_metrics(cfg)
        assert isinstance(provider, MeterProvider)

    def test_is_idempotent(self):
        cfg = _make_metrics_config(exporter="console")
        p1 = configure_metrics(cfg)
        p2 = configure_metrics(cfg)
        assert p1 is p2

    def test_reset_allows_reconfigure(self):
        cfg = _make_metrics_config(exporter="console")
        p1 = configure_metrics(cfg)
        reset_metrics()
        p2 = configure_metrics(cfg)
        assert p1 is not p2

    def test_sets_global_meter_provider(self):
        from opentelemetry import metrics as otel_metrics

        cfg = _make_metrics_config(exporter="console")
        provider = configure_metrics(cfg)
        assert otel_metrics.get_meter_provider() is provider

    def test_creates_metrics_singleton(self):
        cfg = _make_metrics_config(exporter="console")
        configure_metrics(cfg)
        m = get_metrics()
        assert isinstance(m, RAGMetrics)

    def test_get_metrics_raises_before_configure(self):
        with pytest.raises(RuntimeError, match="configure_metrics"):
            get_metrics()

    def test_console_exporter_used_in_dev(self):
        # ConsoleMetricExporter is imported lazily inside _build_metric_exporter.
        # Verify the console path completes without error and produces instruments.
        cfg = _make_metrics_config(exporter="console")
        configure_metrics(cfg)
        m = get_metrics()
        assert m is not None
        assert m.queries_total is not None


# ── get_meter ─────────────────────────────────────────────────────────────────


class TestGetMeter:
    def test_get_meter_returns_meter(self):
        meter = get_meter("rag.test.module")
        assert meter is not None

    def test_get_meter_does_not_require_configure(self):
        # get_meter() uses the global provider (no-op if not configured)
        meter = get_meter("rag.unconfigured")
        assert meter is not None


# ── get_metrics singleton ─────────────────────────────────────────────────────


class TestGetMetricsSingleton:
    def test_returns_same_instance_on_repeated_calls(self):
        cfg = _make_metrics_config(exporter="console")
        configure_metrics(cfg)
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_reset_clears_singleton(self):
        cfg = _make_metrics_config(exporter="console")
        configure_metrics(cfg)
        reset_metrics()
        with pytest.raises(RuntimeError):
            get_metrics()
