"""
Observability package for the LBG RAG Platform.

Three sub-modules, each configured once at application startup:

    from rag.observability.logging import configure_logging, get_logger
    from rag.observability.tracing import configure_tracing, get_tracer, record_span
    from rag.observability.metrics import configure_metrics, get_metrics

Call the configure_* functions in your application entrypoint, in this order:
  1. configure_logging  — must come first so all subsequent log lines are formatted
  2. configure_tracing  — sets global OTel TracerProvider
  3. configure_metrics  — sets global OTel MeterProvider
"""

from rag.observability.logging import configure_logging, get_logger
from rag.observability.metrics import RAGMetrics, configure_metrics, get_metrics, get_meter
from rag.observability.tracing import (
    RAGAttributes,
    configure_tracing,
    get_tracer,
    record_exception,
    record_span,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "configure_tracing",
    "get_tracer",
    "record_span",
    "record_exception",
    "RAGAttributes",
    "configure_metrics",
    "get_metrics",
    "get_meter",
    "RAGMetrics",
]
