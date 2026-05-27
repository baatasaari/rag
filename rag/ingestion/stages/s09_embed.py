"""
Stage 9: Embedding

Calls EmbeddingEngine.embed_for_ingestion() which:
  - Uses RETRIEVAL_DOCUMENT task type (enforced by the engine)
  - Batches chunks up to adapter.max_batch_size
  - Runs batches concurrently up to max_concurrent_batches
  - Applies circuit-breaker and fallback if configured

Sets ctx.embeddings — a parallel list to ctx.chunks where
ctx.embeddings[i] is the vector for ctx.chunks[i].
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


async def embed(ctx: IngestionContext, embedding_engine: Any) -> IngestionContext:
    """Embed all chunks using the primary embedding engine.

    Args:
        ctx:              Current pipeline context.
        embedding_engine: EmbeddingEngine instance.

    Returns:
        Updated context with ctx.embeddings populated.

    Raises:
        Any exception raised by EmbeddingEngine (circuit breaker open, adapter
        failure with no fallback) propagates to the pipeline.
    """
    texts = [c.content for c in ctx.chunks]
    ctx.embeddings = await embedding_engine.embed_for_ingestion(texts)

    log.info(
        "ingestion.embed.ok",
        source_uri=ctx.source_uri,
        chunk_count=len(texts),
        embedding_dim=len(ctx.embeddings[0]) if ctx.embeddings else 0,
    )
    return ctx
