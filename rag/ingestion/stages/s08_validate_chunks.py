"""
Stage 8: Chunk Validation

Filters and caps the chunk list produced by Stage 7:
  - Drop chunks whose content is shorter than min_chunk_length characters.
  - Cap the total chunk count at max_chunks_per_document (log a warning if
    truncation occurs — this usually indicates a chunking misconfiguration).
  - If no valid chunks remain, call ctx.abort() — the pipeline will skip
    persistence and go straight to audit.

Updates ctx.chunks in place.
"""

from __future__ import annotations

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

_DEFAULT_MIN_CHUNK_LENGTH = 20
_DEFAULT_MAX_CHUNKS = 2_000


def validate_chunks(
    ctx: IngestionContext,
    *,
    min_chunk_length: int = _DEFAULT_MIN_CHUNK_LENGTH,
    max_chunks: int = _DEFAULT_MAX_CHUNKS,
) -> IngestionContext:
    """Filter and cap ctx.chunks.

    Args:
        ctx:              Current pipeline context.
        min_chunk_length: Minimum character length for a chunk to be kept.
        max_chunks:       Maximum number of chunks to store per document.

    Returns:
        Updated context.  ctx.abort() called if no valid chunks remain.
    """
    before = len(ctx.chunks)
    ctx.chunks = [c for c in ctx.chunks if len(c.content.strip()) >= min_chunk_length]
    dropped = before - len(ctx.chunks)

    if dropped:
        log.info(
            "ingestion.validate_chunks.dropped_short",
            source_uri=ctx.source_uri,
            dropped=dropped,
            remaining=len(ctx.chunks),
        )

    if len(ctx.chunks) > max_chunks:
        log.warning(
            "ingestion.validate_chunks.truncated",
            source_uri=ctx.source_uri,
            original=len(ctx.chunks),
            max_chunks=max_chunks,
        )
        ctx.chunks = ctx.chunks[:max_chunks]

    if not ctx.chunks:
        ctx.abort(
            f"No valid chunks after filtering (min_chunk_length={min_chunk_length}). "
            "Check the chunking configuration."
        )
        log.warning("ingestion.validate_chunks.no_chunks", source_uri=ctx.source_uri)

    return ctx
