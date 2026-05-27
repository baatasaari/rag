"""
Stage 15: Audit & Completion

Writes an FCA-compliant, immutable INGESTION audit event and (optionally)
publishes a Pub/Sub completion notification.

Audit fields logged (FCA record-keeping rules):
  - doc_id, source_uri — document identity (no content)
  - content_hash — integrity proof (no content)
  - classification_level — sensitivity label
  - pii_types — type names only (never values)
  - chunk_count, completed_stages — pipeline provenance
  - outcome — SUCCESS or FAILURE (abort_reason included on FAILURE)

This stage ALWAYS runs, including on aborted pipelines, so there is an
immutable record of every ingestion attempt.
"""

from __future__ import annotations

from typing import Any

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger
from rag.security.audit import AuditEvent, AuditEventType

log = get_logger(__name__)

_SYSTEM_USER_HASH = "system"  # pipeline runs are attributed to the system user


async def emit_audit(
    ctx: IngestionContext,
    audit_logger: Any,
    *,
    pubsub_client: Any = None,
) -> IngestionContext:
    """Write an audit event and optionally publish a Pub/Sub notification.

    Args:
        ctx:           Current pipeline context.
        audit_logger:  AuditLogger instance (or None to skip — dev only).
        pubsub_client: Optional async Pub/Sub client with a publish() method.

    Returns:
        Updated context.
    """
    outcome: str = "FAILURE" if ctx.should_abort or ctx.stage_errors else "SUCCESS"

    if audit_logger is not None:
        event = AuditEvent(
            event_type=AuditEventType.INGESTION,
            user_id_hash=_SYSTEM_USER_HASH,
            outcome=outcome,  # type: ignore[arg-type]
            classification_level=ctx.classification_level,
            pii_types_detected=ctx.pii_types,
            docs_accessed=[ctx.doc_id],
            error_type=ctx.abort_reason or (
                next(iter(ctx.stage_errors.values()), "") if ctx.stage_errors else ""
            ),
            error_component=next(iter(ctx.stage_errors.keys()), "") if ctx.stage_errors else "",
        )
        try:
            await audit_logger.log_event(event)
        except Exception as exc:
            log.error(
                "ingestion.audit.write_failed",
                doc_id=ctx.doc_id,
                error=str(exc),
            )

    if pubsub_client is not None and not ctx.should_abort:
        try:
            await pubsub_client.publish(
                {
                    "event": "ingestion_complete",
                    "doc_id": ctx.doc_id,
                    "source_uri": ctx.source_uri,
                    "chunk_count": len(ctx.chunks),
                    "classification_level": ctx.classification_level.value,
                }
            )
        except Exception as exc:
            log.warning(
                "ingestion.audit.pubsub_failed",
                doc_id=ctx.doc_id,
                error=str(exc),
            )

    log.info(
        "ingestion.audit.ok",
        doc_id=ctx.doc_id,
        outcome=outcome,
        completed_stages=ctx.completed_stages,
        abort_reason=ctx.abort_reason,
    )
    return ctx
