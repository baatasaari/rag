"""
Stage 1: Source Validation

Checks that the incoming document is safe to ingest:
  - source_uri is non-empty
  - raw_content is present and within the configured size limit
  - MIME type is among the supported set

Sets ctx.mime_type.  Raises ValueError on hard validation failure (pipeline
will abort and record the error).
"""

from __future__ import annotations

import mimetypes

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

_DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
_SUPPORTED_MIME_TYPES = frozenset(
    [
        "text/plain",
        "text/html",
        "text/markdown",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/json",
        "text/csv",
    ]
)


def validate(
    ctx: IngestionContext,
    *,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    supported_mime_types: frozenset[str] = _SUPPORTED_MIME_TYPES,
) -> IngestionContext:
    """Validate source and detect MIME type.

    Args:
        ctx:                  Current pipeline context.
        max_bytes:            Maximum raw_content size in bytes.
        supported_mime_types: Set of accepted MIME types.

    Returns:
        Updated context with ctx.mime_type set.

    Raises:
        ValueError: If the document fails any validation check.
    """
    if not ctx.source_uri:
        raise ValueError("source_uri must not be empty")

    if ctx.raw_content is None:
        raise ValueError(f"No content provided for source_uri={ctx.source_uri!r}")

    content_len = len(ctx.raw_content)
    if content_len > max_bytes:
        raise ValueError(
            f"Document exceeds size limit: {content_len} bytes > {max_bytes} bytes "
            f"(source_uri={ctx.source_uri!r})"
        )

    # Detect MIME type from URI extension; fall back to text/plain.
    mime, _ = mimetypes.guess_type(ctx.source_uri)
    ctx.mime_type = mime or "text/plain"

    if ctx.mime_type not in supported_mime_types:
        raise ValueError(
            f"Unsupported MIME type {ctx.mime_type!r} for source_uri={ctx.source_uri!r}. "
            f"Supported: {sorted(supported_mime_types)}"
        )

    log.info(
        "ingestion.validate.ok",
        source_uri=ctx.source_uri,
        mime_type=ctx.mime_type,
        bytes=content_len,
    )
    return ctx
