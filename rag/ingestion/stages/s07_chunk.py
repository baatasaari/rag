"""
Stage 7: Chunking

Delegates to the injected ChunkingEngine which reads ChunkingConfig.strategy
and applies the appropriate chunking algorithm.

Sets ctx.chunks.
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


def chunk(ctx: IngestionContext, chunking_engine: Any) -> IngestionContext:
    """Split ctx.effective_text into Chunk objects.

    Args:
        ctx:             Current pipeline context.
        chunking_engine: ChunkingEngine instance.

    Returns:
        Updated context with ctx.chunks populated.
    """
    text = ctx.effective_text
    ctx.chunks = chunking_engine.chunk(text, doc_id=ctx.doc_id)
    log.info(
        "ingestion.chunk.ok",
        source_uri=ctx.source_uri,
        chunk_count=len(ctx.chunks),
    )
    return ctx
