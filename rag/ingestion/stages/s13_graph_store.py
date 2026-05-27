"""
Stage 13: Graph Store Upsert (soft — failure does not abort the pipeline)

Writes the document and its chunks as nodes in Neo4j, with typed relationships:
  - (Document) -[:CONTAINS]-> (Chunk)
  - (Chunk)    -[:PARENT_OF]-> (Chunk)   [hierarchical strategy only]

Node properties:
  Document: id, source_uri, classification_level, ingestion_timestamp
  Chunk:    id, content, chunk_index, level, parent_id

Failures here are logged but do not abort the pipeline because the graph
store is supplementary — core retrieval uses the vector store (Stage 11).
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


async def upsert_graph(ctx: IngestionContext, graph_store: Any) -> IngestionContext:
    """Upsert document and chunk nodes into the graph store.

    Args:
        ctx:         Current pipeline context.
        graph_store: Neo4jGraphStore instance (or None to skip).

    Returns:
        Updated context.
    """
    if graph_store is None:
        return ctx

    # Upsert Document node.
    await graph_store.upsert_node(
        "Document",
        {
            "id": ctx.doc_id,
            "source_uri": ctx.source_uri,
            "classification_level": ctx.classification_level.value,
            "ingestion_timestamp": ctx.ingestion_timestamp.isoformat(),
        },
    )

    for chunk in ctx.chunks:
        chunk_node_id = f"{ctx.doc_id}:chunk:{chunk.chunk_index}"

        await graph_store.upsert_node(
            "Chunk",
            {
                "id": chunk_node_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "level": chunk.level,
            },
        )

        await graph_store.upsert_edge(
            ctx.doc_id, chunk_node_id, "CONTAINS", {}
        )

        if chunk.parent_id:
            await graph_store.upsert_edge(
                chunk.parent_id, chunk_node_id, "PARENT_OF", {}
            )

    log.info(
        "ingestion.upsert_graph.ok",
        doc_id=ctx.doc_id,
        chunk_count=len(ctx.chunks),
    )
    return ctx
