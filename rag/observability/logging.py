"""
Structured logging for the LBG RAG Platform.

Wraps structlog with:
  - JSON renderer (structured=True) or ConsoleRenderer (local dev)
  - OTel trace context injection (trace_id + span_id) for log-trace correlation
  - Sensitive field masking: HMAC-hash user IDs, redact credential fields
  - Service metadata on every log line (service, version, environment)
  - stdlib bridge so third-party library logs flow through the same chain

Usage:
    configure_logging(config.observability, service_name="lbg-rag", ...)
    log = get_logger(__name__)
    log.info("retrieval.complete", chunk_count=12, latency_ms=42)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from rag.core.schemas import LogLevel, ObservabilityConfig

# ---------------------------------------------------------------------------
# HMAC key for pseudonymising user IDs in log lines.
# Set RAG_LOG_HMAC_KEY in all environments so hashes are consistent across
# worker processes and log-rotation windows. If unset a process-local random
# key is generated, which is acceptable only for single-process dev runs.
# ---------------------------------------------------------------------------
_HMAC_KEY: bytes = (os.getenv("RAG_LOG_HMAC_KEY") or "").encode() or os.urandom(32)

_SENSITIVE_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "token",
        "api_key",
        "apikey",
        "secret",
        "credential",
        "private_key",
        "access_key",
        "connection_string",
        "conn_str",
        "auth_header",
    }
)

_USER_ID_FIELDS: frozenset[str] = frozenset(
    {"user_id", "userid", "sub", "subject", "user_hash"}
)

_LEVEL_MAP: dict[LogLevel, int] = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}

_configured: bool = False


# ---------------------------------------------------------------------------
# Processor functions
# ---------------------------------------------------------------------------


def _mask_sensitive(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Redact credential-like fields; HMAC-hash user identity fields.

    Operates on the top-level event_dict only — nested dicts are not walked
    (nested secrets should not appear in log calls at all).
    """
    for key in list(event_dict):
        lower = key.lower()
        if any(s in lower for s in _SENSITIVE_SUBSTRINGS):
            event_dict[key] = "[REDACTED]"
        elif lower in _USER_ID_FIELDS:
            raw = str(event_dict[key])
            event_dict[key] = _hmac_hash(raw)
    return event_dict


def _hmac_hash(value: str) -> str:
    """Return a 16-char HMAC-SHA256 hex prefix of value."""
    return hmac.new(_HMAC_KEY, value.encode(), hashlib.sha256).hexdigest()[:16]


def _make_trace_context_processor(include: bool) -> Processor:
    """Return a processor that injects OTel trace_id and span_id if include=True."""

    def _processor(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
        if not include:
            return event_dict
        try:
            from opentelemetry import trace  # local import avoids hard dependency at module load

            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx.is_valid:
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
                event_dict["span_id"] = format(ctx.span_id, "016x")
        except Exception:  # noqa: BLE001 — never break logging
            pass
        return event_dict

    return _processor


def _make_service_info_processor(service: str, version: str, environment: str) -> Processor:
    def _processor(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service)
        event_dict.setdefault("version", version)
        event_dict.setdefault("environment", environment)
        return event_dict

    return _processor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def configure_logging(
    config: ObservabilityConfig,
    *,
    service_name: str = "lbg-rag-platform",
    service_version: str = "1.0.0",
    environment: str = "unknown",
) -> None:
    """Configure structlog + stdlib logging.

    Idempotent — safe to call multiple times; subsequent calls after the first
    are no-ops. Call once during application startup before any log statement.
    """
    global _configured
    if _configured:
        return

    log_cfg = config.logging
    level = _LEVEL_MAP.get(log_cfg.level, logging.INFO)

    # Wire stdlib root logger so third-party library logs are captured.
    logging.basicConfig(level=level, format="%(message)s", force=True)
    logging.getLogger().setLevel(level)

    renderer: Processor
    if log_cfg.structured:
        # ExceptionRenderer serialises exc_info as a structured dict — better
        # than a raw string for Cloud Logging's JSON parser.
        exception_processor: Processor = structlog.processors.ExceptionRenderer()
        renderer = structlog.processors.JSONRenderer()
    else:
        exception_processor = structlog.dev.set_exc_info
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _make_trace_context_processor(log_cfg.include_trace_context),
        _mask_sensitive,
        _make_service_info_processor(service_name, service_version, environment),
        structlog.processors.StackInfoRenderer(),
        exception_processor,
        renderer,
    ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger for the given module name.

    If configure_logging() has not been called, structlog uses its default
    (dev) configuration — acceptable for test runs and scripts.
    """
    return structlog.get_logger(name)  # type: ignore[return-value]


def reset_logging() -> None:
    """Reset logging state. FOR TESTING ONLY."""
    global _configured
    _configured = False
    structlog.reset_defaults()
