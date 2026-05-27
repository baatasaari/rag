"""
Stage 12: Document Store Upsert

Writes document-level metadata to AlloyDB document_store:
  - doc_id, source_uri, content_hash, classification_level
  - allowed_roles, pii_types (types only — no values), pii_risk_level
  - chunk_count, mime_type, ingestion_timestamp

This record enables:
  - Duplicate detection on subsequent ingestions (via content_hash)
  - Document provenance queries
  - Audit trail cross-referencing
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


async def upsert_document(ctx: IngestionContext, document_store: Any) -> IngestionContext:
    """Upsert document metadata into the document store.

    Args:
        ctx:            Current pipeline context.
        document_store: AlloyDBDocumentStore instance.

    Returns:
        Updated context (document record written to store).
    """
    doc = {
        "doc_id": ctx.doc_id,
        "source_uri": ctx.source_uri,
        "content_hash": ctx.content_hash,
        "classification_level": ctx.classification_level.value,
        "allowed_roles": ctx.allowed_roles,
        "metadata": {
            "pii_types": ctx.pii_types,       # types only — FCA compliant
            "pii_risk_level": ctx.pii_risk_level,
            "chunk_count": len(ctx.chunks),
            "mime_type": ctx.mime_type,
            "ingestion_timestamp": ctx.ingestion_timestamp.isoformat(),
        },
    }

    await document_store.put(doc)
    log.info(
        "ingestion.upsert_document.ok",
        doc_id=ctx.doc_id,
        source_uri=ctx.source_uri,
    )
    return ctx
