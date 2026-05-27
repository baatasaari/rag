"""
Stage 6: Duplicate Detection

Computes a SHA-256 fingerprint of the sanitised text and checks the document
store for an existing document with the same hash.

If a duplicate is found, ctx.abort() is called with a descriptive reason — the
pipeline will skip straight to Stage 15 (audit) and record the skip.

Sets ctx.content_hash and ctx.is_duplicate.
"""

from __future__ import annotations

import hashlib
from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)


async def deduplicate(ctx: IngestionContext, document_store: Any) -> IngestionContext:
    """Hash content and check for duplicates in the document store.

    Args:
        ctx:            Current pipeline context.
        document_store: AlloyDBDocumentStore (or compatible) instance.

    Returns:
        Updated context.  ctx.is_duplicate=True and ctx.abort_reason set if
        a duplicate is found.
    """
    text = ctx.effective_text.encode("utf-8")
    ctx.content_hash = hashlib.sha256(text).hexdigest()

    existing = await document_store.get_by_hash(ctx.content_hash)
    if existing is not None:
        ctx.is_duplicate = True
        existing_id = getattr(existing, "doc_id", str(existing))
        ctx.abort(f"Duplicate of existing document {existing_id!r}")
        log.info(
            "ingestion.duplicate_detected",
            # Log hash prefix only — never the full content.
            content_hash_prefix=ctx.content_hash[:12] + "...",
            existing_doc_id=existing_id,
        )
    else:
        log.info(
            "ingestion.deduplicate.unique",
            content_hash_prefix=ctx.content_hash[:12] + "...",
        )

    return ctx
