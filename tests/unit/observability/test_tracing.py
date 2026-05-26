"""
Tests for rag.observability.tracing — spans, exception recording, tail sampling.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from rag.observability.tracing import (
    RAGAttributes,
    TailSamplingSpanProcessor,
    configure_tracing,
    get_tracer,
    record_exception,
    record_span,
    reset_tracing,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_trace_state():
    reset_tracing()
    yield
    reset_tracing()


@pytest.fixture()
def in_memory_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """A TracerProvider wired to an in-memory exporter, set as global provider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)
    return provider, exporter


def _make_trace_config(
    *,
    exporter: str = "console",
    sampling_rate: float = 1.0,
    always_sample_errors: bool = True,
    always_sample_slow_ms: int = 3000,
    endpoint: str | None = None,
):
    cfg = MagicMock()
    cfg.tracing.exporter = exporter
    cfg.tracing.sampling_rate = sampling_rate
    cfg.tracing.always_sample_errors = always_sample_errors
    cfg.tracing.always_sample_slow_requests_ms = always_sample_slow_ms
    cfg.tracing.endpoint = endpoint
    return cfg


# ── RAGAttributes ─────────────────────────────────────────────────────────────


class TestRAGAttributes:
    def test_query_id_defined(self):
        assert RAGAttributes.QUERY_ID == "rag.query_id"

    def test_latency_ms_defined(self):
        assert RAGAttributes.LATENCY_MS == "rag.latency_ms"

    def test_pattern_defined(self):
        assert RAGAttributes.PATTERN == "rag.pattern"

    def test_cache_hit_defined(self):
        assert RAGAttributes.CACHE_HIT == "rag.cache_hit"

    def test_tokens_in_defined(self):
        assert RAGAttributes.TOKENS_IN == "rag.tokens.input"

    def test_tokens_out_defined(self):
        assert RAGAttributes.TOKENS_OUT == "rag.tokens.output"

    def test_retrieval_strategy_defined(self):
        assert RAGAttributes.RETRIEVAL_STRATEGY == "rag.retrieval.strategy"

    def test_model_defined(self):
        assert RAGAttributes.MODEL == "rag.model"

    def test_all_attribute_values_start_with_rag(self):
        import dataclasses

        # RAGAttributes was instantiated as a singleton — check all string fields
        for field in dataclasses.fields(type(RAGAttributes)):
            value = getattr(RAGAttributes, field.name)
            assert isinstance(value, str) and value.startswith("rag."), (
                f"RAGAttributes.{field.name} = {value!r} does not start with 'rag.'"
            )


# ── get_tracer ────────────────────────────────────────────────────────────────


class TestGetTracer:
    def test_get_tracer_returns_tracer(self, in_memory_provider):
        tracer = get_tracer("rag.test")
        assert tracer is not None

    def test_get_tracer_creates_spans(self, in_memory_provider):
        provider, exporter = in_memory_provider
        tracer = get_tracer("rag.test")
        with tracer.start_as_current_span("test-span"):
            pass
        spans = exporter.get_finished_spans()
        assert any(s.name == "test-span" for s in spans)


# ── record_span ───────────────────────────────────────────────────────────────


class TestRecordSpan:
    def test_span_is_created(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with record_span("embedding.embed"):
            pass
        spans = exporter.get_finished_spans()
        assert any(s.name == "embedding.embed" for s in spans)

    def test_attributes_set_on_span(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with record_span("retrieval.search", **{RAGAttributes.RETRIEVAL_STRATEGY: "hybrid"}):
            pass
        spans = exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "retrieval.search")
        assert span.attributes[RAGAttributes.RETRIEVAL_STRATEGY] == "hybrid"

    def test_latency_ms_recorded_on_exit(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with record_span("generation.generate"):
            pass
        spans = exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "generation.generate")
        assert RAGAttributes.LATENCY_MS in span.attributes
        assert span.attributes[RAGAttributes.LATENCY_MS] >= 0

    def test_exception_marks_span_error(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with pytest.raises(ValueError):
            with record_span("test.op"):
                raise ValueError("boom")
        spans = exporter.get_finished_spans()
        span = spans[-1]
        assert span.status.status_code == StatusCode.ERROR

    def test_exception_is_reraised(self, in_memory_provider):
        with pytest.raises(RuntimeError, match="original error"):
            with record_span("test.op"):
                raise RuntimeError("original error")

    def test_exception_event_recorded(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with pytest.raises(KeyError):
            with record_span("test.op"):
                raise KeyError("missing")
        spans = exporter.get_finished_spans()
        span = spans[-1]
        event_names = [e.name for e in span.events]
        assert "exception" in event_names

    def test_span_yields_span_object(self, in_memory_provider):
        with record_span("test.op") as span:
            assert span is not None
            span.set_attribute("custom.key", "value")

    def test_none_attributes_not_set(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with record_span("test.op", **{RAGAttributes.QUERY_ID: None}):
            pass
        spans = exporter.get_finished_spans()
        span = spans[-1]
        assert RAGAttributes.QUERY_ID not in (span.attributes or {})

    def test_nested_spans_have_parent_child_relationship(self, in_memory_provider):
        provider, exporter = in_memory_provider
        with record_span("parent.op") as parent_span:
            with record_span("child.op") as child_span:
                pass
        spans = exporter.get_finished_spans()
        child = next(s for s in spans if s.name == "child.op")
        parent = next(s for s in spans if s.name == "parent.op")
        assert child.parent is not None
        assert child.parent.span_id == parent.context.span_id


# ── record_exception ──────────────────────────────────────────────────────────


class TestRecordException:
    def test_sets_error_status(self, in_memory_provider):
        provider, exporter = in_memory_provider
        tracer = get_tracer("test")
        with tracer.start_as_current_span("op") as span:
            exc = ValueError("bad input")
            record_exception(span, exc)
        spans = exporter.get_finished_spans()
        assert spans[-1].status.status_code == StatusCode.ERROR

    def test_sets_error_type_attribute(self, in_memory_provider):
        provider, exporter = in_memory_provider
        tracer = get_tracer("test")
        with tracer.start_as_current_span("op") as span:
            record_exception(span, TypeError("wrong type"))
        spans = exporter.get_finished_spans()
        assert spans[-1].attributes.get(RAGAttributes.ERROR_TYPE) == "TypeError"

    def test_exception_description_in_status(self, in_memory_provider):
        provider, exporter = in_memory_provider
        tracer = get_tracer("test")
        with tracer.start_as_current_span("op") as span:
            record_exception(span, ValueError("detail message"))
        spans = exporter.get_finished_spans()
        assert "detail message" in spans[-1].status.description


# ── TailSamplingSpanProcessor ─────────────────────────────────────────────────


class TestTailSamplingSpanProcessor:
    def _make_span(self, *, error: bool = False, latency_ms: float = 0.0) -> MagicMock:
        span = MagicMock()
        span.context = MagicMock()
        span.context.is_valid = True
        # Not sampled — tail processor should decide
        span.context.trace_flags.sampled = False
        span.status.status_code = StatusCode.ERROR if error else StatusCode.OK
        span.attributes = {RAGAttributes.LATENCY_MS: latency_ms}
        return span

    def test_error_span_is_exported_when_enabled(self):
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=True,
            always_sample_slow_ms=3000,
        )
        span = self._make_span(error=True)
        processor.on_end(span)
        exporter.export.assert_called_once()

    def test_error_span_not_exported_when_disabled(self):
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=False,
            always_sample_slow_ms=0,
        )
        span = self._make_span(error=True)
        processor.on_end(span)
        exporter.export.assert_not_called()

    def test_slow_span_exported_when_exceeds_threshold(self):
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=False,
            always_sample_slow_ms=1000,
        )
        span = self._make_span(latency_ms=2000.0)
        processor.on_end(span)
        exporter.export.assert_called_once()

    def test_fast_ok_span_not_exported(self):
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=True,
            always_sample_slow_ms=3000,
        )
        span = self._make_span(error=False, latency_ms=50.0)
        processor.on_end(span)
        exporter.export.assert_not_called()

    def test_sampled_span_not_double_exported(self):
        """Spans already sampled (batch processor handles them) must be skipped."""
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=True,
            always_sample_slow_ms=1000,
        )
        span = self._make_span(error=True, latency_ms=5000.0)
        span.context.trace_flags.sampled = True  # already sampled
        processor.on_end(span)
        exporter.export.assert_not_called()

    def test_invalid_context_skipped(self):
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=True,
            always_sample_slow_ms=1000,
        )
        span = self._make_span(error=True)
        span.context.is_valid = False
        processor.on_end(span)
        exporter.export.assert_not_called()

    def test_none_context_skipped(self):
        exporter = MagicMock()
        processor = TailSamplingSpanProcessor(
            exporter,
            always_sample_errors=True,
            always_sample_slow_ms=1000,
        )
        span = MagicMock()
        span.context = None
        processor.on_end(span)
        exporter.export.assert_not_called()


# ── configure_tracing ─────────────────────────────────────────────────────────


class TestConfigureTracing:
    def test_returns_tracer_provider(self):
        cfg = _make_trace_config(exporter="console")
        provider = configure_tracing(cfg)
        assert isinstance(provider, TracerProvider)

    def test_is_idempotent(self):
        cfg = _make_trace_config(exporter="console")
        p1 = configure_tracing(cfg)
        p2 = configure_tracing(cfg)
        assert p1 is p2

    def test_reset_allows_reconfigure(self):
        cfg = _make_trace_config(exporter="console")
        p1 = configure_tracing(cfg)
        reset_tracing()
        p2 = configure_tracing(cfg)
        assert p1 is not p2

    def test_console_exporter_used_in_dev(self):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        cfg = _make_trace_config(exporter="console")
        with patch(
            "rag.observability.tracing.ConsoleSpanExporter",
            wraps=ConsoleSpanExporter,
        ) as mock_cls:
            configure_tracing(cfg)
        assert mock_cls.called

    def test_tail_sampling_processor_added_when_enabled(self):
        cfg = _make_trace_config(
            exporter="console",
            always_sample_errors=True,
            always_sample_slow_ms=3000,
        )
        provider = configure_tracing(cfg)
        processor_types = [type(p).__name__ for p in provider._active_span_processor._span_processors]
        assert "TailSamplingSpanProcessor" in processor_types

    def test_sets_global_tracer_provider(self):
        cfg = _make_trace_config(exporter="console")
        provider = configure_tracing(cfg)
        assert otel_trace.get_tracer_provider() is provider
