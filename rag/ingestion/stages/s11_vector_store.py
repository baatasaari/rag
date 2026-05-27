"""
Stage 11: Vector Store Upsert

Writes chunk embeddings to AlloyDB pgvector.  Each chunk becomes one row with:
  - chunk_id:      "{doc_id}:chunk:{chunk_index}"
  - doc_id:        ctx.doc_id
  - content:       chunk.content
  - embedding:     the float vector from Stage 9
  - metadata:      classification_level, source_uri, ingestion_timestamp,
                   chunk_index, parent_id, level, plus any chunk-level metadata
  - allowed_roles: from Stage 10 (enforced server-side at retrieval)
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


async def upsert_vectors(ctx: IngestionContext, vector_store: Any) -> IngestionContext:
    """Upsert all chunk embeddings into the vector store.

    Args:
        ctx:          Current pipeline context.
        vector_store: AlloyDBVectorStore instance.

    Returns:
        Updated context (chunks/embeddings unchanged; store records written).
    """
    records = [
        {
            "chunk_id": f"{ctx.doc_id}:chunk:{chunk.chunk_index}",
            "doc_id": ctx.doc_id,
            "content": chunk.content,
            "embedding": embedding,
            "metadata": {
                **chunk.metadata,
                "classification_level": ctx.classification_level.value,
                "source_uri": ctx.source_uri,
                "ingestion_timestamp": ctx.ingestion_timestamp.isoformat(),
                "chunk_index": chunk.chunk_index,
                "parent_id": chunk.parent_id,
                "level": chunk.level,
            },
            "allowed_roles": ctx.allowed_roles,
        }
        for chunk, embedding in zip(ctx.chunks, ctx.embeddings)
    ]

    await vector_store.upsert(records)
    log.info(
        "ingestion.upsert_vectors.ok",
        source_uri=ctx.source_uri,
        record_count=len(records),
    )
    return ctx
