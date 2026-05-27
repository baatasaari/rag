"""
Stage 14: Cache Invalidation (soft — failure does not abort the pipeline)

Evicts any semantic cache entries keyed to this document so subsequent queries
retrieve freshly-indexed content rather than stale cached responses.

Soft stage: if the cache is unavailable or returns an error, a warning is
logged and the pipeline continues.
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


async def invalidate_cache(ctx: IngestionContext, cache: Any) -> IngestionContext:
    """Invalidate cache entries for this document.

    Args:
        ctx:   Current pipeline context.
        cache: RedisSemanticCache instance (or None to skip).

    Returns:
        Updated context.
    """
    if cache is None:
        return ctx

    try:
        evicted = await cache.invalidate(ctx.doc_id)
        log.info(
            "ingestion.cache_invalidated",
            doc_id=ctx.doc_id,
            evicted_keys=evicted,
        )
    except Exception as exc:
        log.warning(
            "ingestion.cache_invalidate_failed",
            doc_id=ctx.doc_id,
            error=str(exc),
        )

    return ctx
