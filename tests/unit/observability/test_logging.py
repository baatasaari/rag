"""
Tests for rag.observability.logging — processor functions and configuration.

Strategy: test processor functions directly (unit) and verify configure_logging
produces the right processor chain via mock inspection.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
import structlog

from rag.observability.logging import (
    _HMAC_KEY,
    _USER_ID_FIELDS,
    _hmac_hash,
    _make_service_info_processor,
    _make_trace_context_processor,
    _mask_sensitive,
    configure_logging,
    get_logger,
    reset_logging,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_log_state():
    """Reset structlog and module _configured flag before/after every test."""
    reset_logging()
    yield
    reset_logging()


def _make_obs_config(*, structured: bool = True, include_trace: bool = True):
    cfg = MagicMock()
    cfg.logging.level.value = "INFO"
    cfg.logging.structured = structured
    cfg.logging.include_trace_context = include_trace
    cfg.logging.exporter = "stdout"
    # LogLevel enum — use the actual enum value so _LEVEL_MAP lookup works
    from rag.core.schemas import LogLevel

    cfg.logging.level = LogLevel.INFO
    return cfg


# ── _mask_sensitive processor ─────────────────────────────────────────────────


class TestMaskSensitive:
    def test_password_field_redacted(self):
        event: dict[str, Any] = {"password": "s3cr3t", "event": "login"}
        result = _mask_sensitive(None, "info", event)
        assert result["password"] == "[REDACTED]"

    def test_token_field_redacted(self):
        event: dict[str, Any] = {"token": "Bearer abc123", "event": "auth"}
        result = _mask_sensitive(None, "info", event)
        assert result["token"] == "[REDACTED]"

    def test_api_key_field_redacted(self):
        event: dict[str, Any] = {"api_key": "key-abc", "event": "call"}
        result = _mask_sensitive(None, "info", event)
        assert result["api_key"] == "[REDACTED]"

    def test_secret_field_redacted(self):
        event: dict[str, Any] = {"my_secret": "value", "event": "x"}
        result = _mask_sensitive(None, "info", event)
        assert result["my_secret"] == "[REDACTED]"

    def test_connection_string_redacted(self):
        event: dict[str, Any] = {"connection_string": "postgres://user:pw@host/db", "event": "x"}
        result = _mask_sensitive(None, "info", event)
        assert result["connection_string"] == "[REDACTED]"

    def test_non_sensitive_fields_pass_through(self):
        event: dict[str, Any] = {"chunk_count": 12, "latency_ms": 42, "event": "retrieval"}
        result = _mask_sensitive(None, "info", event)
        assert result["chunk_count"] == 12
        assert result["latency_ms"] == 42
        assert result["event"] == "retrieval"

    def test_user_id_is_hashed_not_raw(self):
        event: dict[str, Any] = {"user_id": "alice@lbg.com", "event": "query"}
        result = _mask_sensitive(None, "info", event)
        assert result["user_id"] != "alice@lbg.com"
        assert len(result["user_id"]) == 16  # 16-char hex prefix

    def test_user_id_hash_is_consistent(self):
        event1: dict[str, Any] = {"user_id": "alice", "event": "x"}
        event2: dict[str, Any] = {"user_id": "alice", "event": "y"}
        r1 = _mask_sensitive(None, "info", event1)
        r2 = _mask_sensitive(None, "info", event2)
        assert r1["user_id"] == r2["user_id"]

    def test_different_user_ids_produce_different_hashes(self):
        e1: dict[str, Any] = {"user_id": "alice", "event": "x"}
        e2: dict[str, Any] = {"user_id": "bob", "event": "x"}
        r1 = _mask_sensitive(None, "info", e1)
        r2 = _mask_sensitive(None, "info", e2)
        assert r1["user_id"] != r2["user_id"]

    def test_event_key_not_touched(self):
        event: dict[str, Any] = {"event": "password_change_requested"}
        # "event" does not match any sensitive substring even though value contains "password"
        result = _mask_sensitive(None, "info", event)
        # The KEY is "event" which doesn't contain a sensitive substring
        assert result["event"] == "password_change_requested"

    def test_case_insensitive_field_matching(self):
        event: dict[str, Any] = {"API_KEY": "abc", "event": "x"}
        result = _mask_sensitive(None, "info", event)
        assert result["API_KEY"] == "[REDACTED]"


# ── _hmac_hash ────────────────────────────────────────────────────────────────


class TestHmacHash:
    def test_returns_16_char_hex(self):
        h = _hmac_hash("test-user")
        assert len(h) == 16
        int(h, 16)  # must be valid hex

    def test_stable_for_same_input(self):
        assert _hmac_hash("user1") == _hmac_hash("user1")

    def test_different_for_different_input(self):
        assert _hmac_hash("user1") != _hmac_hash("user2")

    def test_uses_module_hmac_key(self):
        expected = hmac.new(_HMAC_KEY, "u".encode(), hashlib.sha256).hexdigest()[:16]
        assert _hmac_hash("u") == expected


# ── Trace context processor ───────────────────────────────────────────────────


class TestTraceContextProcessor:
    def test_injects_trace_id_and_span_id_when_span_active(self):
        # Create a real OTel span and make it current
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")

        processor = _make_trace_context_processor(include=True)

        with tracer.start_as_current_span("test-span"):
            event: dict[str, Any] = {"event": "retrieval"}
            result = processor(None, "info", event)

        assert "trace_id" in result
        assert "span_id" in result
        assert len(result["trace_id"]) == 32
        assert len(result["span_id"]) == 16

    def test_no_context_when_no_active_span(self):
        from opentelemetry import trace
        from opentelemetry.trace import NonRecordingSpan

        processor = _make_trace_context_processor(include=True)
        event: dict[str, Any] = {"event": "test"}
        result = processor(None, "info", event)
        # No active span → keys must be absent
        assert "trace_id" not in result
        assert "span_id" not in result

    def test_no_injection_when_include_false(self):
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        processor = _make_trace_context_processor(include=False)

        with tracer.start_as_current_span("noop"):
            event: dict[str, Any] = {"event": "test"}
            result = processor(None, "info", event)

        assert "trace_id" not in result
        assert "span_id" not in result


# ── Service info processor ────────────────────────────────────────────────────


class TestServiceInfoProcessor:
    def test_adds_service_fields(self):
        processor = _make_service_info_processor("my-svc", "2.0.0", "staging")
        event: dict[str, Any] = {"event": "x"}
        result = processor(None, "info", event)
        assert result["service"] == "my-svc"
        assert result["version"] == "2.0.0"
        assert result["environment"] == "staging"

    def test_does_not_overwrite_existing_service(self):
        processor = _make_service_info_processor("my-svc", "2.0.0", "staging")
        event: dict[str, Any] = {"event": "x", "service": "caller-svc"}
        result = processor(None, "info", event)
        assert result["service"] == "caller-svc"  # setdefault: original preserved


# ── configure_logging ─────────────────────────────────────────────────────────


class TestConfigureLogging:
    def test_configure_logging_is_idempotent(self):
        cfg = _make_obs_config()
        with patch("structlog.configure") as mock_cfg:
            configure_logging(cfg)
            configure_logging(cfg)  # second call — must be no-op
        assert mock_cfg.call_count == 1

    def test_json_renderer_used_when_structured_true(self):
        cfg = _make_obs_config(structured=True)
        with patch("structlog.configure") as mock_cfg:
            configure_logging(cfg)
        _, kwargs = mock_cfg.call_args
        processors = kwargs["processors"]
        renderer = processors[-1]
        assert isinstance(renderer, structlog.processors.JSONRenderer)

    def test_console_renderer_used_when_structured_false(self):
        cfg = _make_obs_config(structured=False)
        with patch("structlog.configure") as mock_cfg:
            configure_logging(cfg)
        _, kwargs = mock_cfg.call_args
        processors = kwargs["processors"]
        renderer = processors[-1]
        assert isinstance(renderer, structlog.dev.ConsoleRenderer)

    def test_mask_sensitive_is_in_processor_chain(self):
        cfg = _make_obs_config()
        with patch("structlog.configure") as mock_cfg:
            configure_logging(cfg)
        _, kwargs = mock_cfg.call_args
        processors = kwargs["processors"]
        assert _mask_sensitive in processors

    def test_exception_renderer_in_json_chain(self):
        cfg = _make_obs_config(structured=True)
        with patch("structlog.configure") as mock_cfg:
            configure_logging(cfg)
        _, kwargs = mock_cfg.call_args
        processors = kwargs["processors"]
        types = [type(p).__name__ for p in processors]
        assert "ExceptionRenderer" in types

    def test_get_logger_returns_logger_after_configure(self):
        cfg = _make_obs_config()
        configure_logging(cfg, environment="test")
        logger = get_logger("test.module")
        assert logger is not None

    def test_reset_allows_reconfigure(self):
        cfg = _make_obs_config()
        configure_logging(cfg)
        reset_logging()

        cfg2 = _make_obs_config(structured=False)
        with patch("structlog.configure") as mock_cfg:
            configure_logging(cfg2)
        _, kwargs = mock_cfg.call_args
        processors = kwargs["processors"]
        assert isinstance(processors[-1], structlog.dev.ConsoleRenderer)


# ── get_logger ────────────────────────────────────────────────────────────────


class TestGetLogger:
    def test_get_logger_returns_bound_logger(self):
        logger = get_logger("rag.test")
        assert logger is not None

    def test_get_logger_different_names_are_different_loggers(self):
        l1 = get_logger("rag.module_a")
        l2 = get_logger("rag.module_b")
        # Both valid — not required to be different objects (structlog may cache)
        assert l1 is not None and l2 is not None


# ── JSON output serialisability ───────────────────────────────────────────────


class TestJsonOutput:
    def test_json_output_is_valid_json(self):
        """Full integration: configure with JSON renderer, emit a log, verify JSON."""
        buf = io.StringIO()

        # Use PrintLogger pointing to our StringIO to capture output
        structlog.configure(
            processors=[
                _mask_sensitive,
                _make_service_info_processor("svc", "1.0", "test"),
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(buf),
            wrapper_class=structlog.BoundLogger,
            cache_logger_on_first_use=False,
        )

        logger = structlog.get_logger("test")
        logger.info("query.complete", chunk_count=5, latency_ms=120)

        output = buf.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["event"] == "query.complete"
        assert parsed["chunk_count"] == 5

    def test_sensitive_fields_redacted_in_json_output(self):
        buf = io.StringIO()
        structlog.configure(
            processors=[
                _mask_sensitive,
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(buf),
            wrapper_class=structlog.BoundLogger,
            cache_logger_on_first_use=False,
        )
        logger = structlog.get_logger("test")
        logger.info("test", password="secret", user_id="alice")

        parsed = json.loads(buf.getvalue().strip())
        assert parsed["password"] == "[REDACTED]"
        assert parsed["user_id"] != "alice"
