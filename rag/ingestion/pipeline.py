"""
IngestionPipeline — async orchestrator for the 15-stage ingestion workflow.

Each stage is wrapped in an OTel child span.  Stage failures are handled as:
  - Hard stages  → re-raise (caller or Airflow retries the full pipeline run)
  - Soft stages  → log warning, continue  (graph store, cache — supplementary)

Abort flow:
  - Any stage may call ctx.abort(reason) to signal early exit.
  - After abort the pipeline skips straight to Stage 15 (audit) so every
    ingestion attempt — including duplicates and RESTRICTED rejections —
    has an immutable FCA-compliant record.

Usage::

    pipeline = IngestionPipeline(
        config=rag_config,
        chunking_engine=chunking_engine,
        embedding_engine=embedding_engine,
        vector_store=vector_store,
        document_store=document_store,
        graph_store=graph_store,       # optional
        cache=cache,                   # optional
        audit_logger=audit_logger,     # optional
    )
    ctx = await pipeline.run("gs://bucket/doc.pdf", raw_bytes)
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from rag.ingestion.context import IngestionContext, make_doc_id
from rag.ingestion.stages import (
    s01_validate,
    s02_extract,
    s03_pii,
    s04_classify,
    s05_sanitise,
    s06_deduplicate,
    s07_chunk,
    s08_validate_chunks,
    s09_embed,
    s10_rbac,
    s11_vector_store,
    s12_doc_store,
    s13_graph_store,
    s14_cache,
    s15_audit,
)
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)


class IngestionPipeline:
    """Orchestrates the 15 ingestion stages in sequence.

    Args:
        config:           RAGConfig (or compatible object with .ingestion /
                          .security sub-configs).
        chunking_engine:  ChunkingEngine instance.
        embedding_engine: EmbeddingEngine instance.
        vector_store:     AlloyDBVectorStore instance.
        document_store:   AlloyDBDocumentStore instance.
        graph_store:      Neo4jGraphStore (optional — soft stage).
        cache:            RedisSemanticCache (optional — soft stage).
        audit_logger:     AuditLogger (optional; required for FCA compliance).
    """

    def __init__(
        self,
        config: Any,
        chunking_engine: Any,
        embedding_engine: Any,
        vector_store: Any,
        document_store: Any,
        *,
        graph_store: Any = None,
        cache: Any = None,
        audit_logger: Any = None,
    ) -> None:
        self._config = config
        self._chunker = chunking_engine
        self._embedder = embedding_engine
        self._vector_store = vector_store
        self._doc_store = document_store
        self._graph_store = graph_store
        self._cache = cache
        self._audit = audit_logger

        # Security sub-config (optional chaining).
        security = getattr(config, "security", None)
        pii_cfg = getattr(security, "pii_detection", None)
        self._reject_restricted: bool = getattr(pii_cfg, "reject_restricted_data", True)

        # Ingestion sub-config (optional chaining).
        ing_cfg = getattr(config, "ingestion", None)
        clean_cfg = getattr(ing_cfg, "cleaner", None)
        self._min_chunk_length: int = getattr(clean_cfg, "min_content_length", 20)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, source_uri: str, raw_content: bytes) -> IngestionContext:
        """Execute all 15 stages for a single document.

        Returns:
            Completed IngestionContext.  Inspect ctx.should_abort and
            ctx.stage_errors for failure details.
        """
        ctx = IngestionContext(
            source_uri=source_uri,
            doc_id=make_doc_id(source_uri),
            raw_content=raw_content,
        )

        with record_span(
            "ingestion.run",
            **{RAGAttributes.SOURCE_URI: source_uri},
        ) as span:
            # ── Stages 1-5: validate → sanitise (pure computation) ───────
            ctx = await self._stage(ctx, "validate", s01_validate.validate)
            ctx = await self._stage(ctx, "extract", s02_extract.extract_text)
            ctx = await self._stage(ctx, "detect_pii", s03_pii.detect_pii)
            ctx = await self._stage(ctx, "classify", s04_classify.classify)
            ctx = await self._stage(ctx, "sanitise", s05_sanitise.sanitise)

            # ── Stage 6: duplicate detection ─────────────────────────────
            ctx = await self._stage(
                ctx, "deduplicate",
                lambda c: s06_deduplicate.deduplicate(c, self._doc_store),
                is_async=True,
            )
            if ctx.should_abort:
                span.set_attribute("rag.ingestion.aborted", True)
                await self._finalise(ctx)
                return ctx

            # ── Stages 7-8: chunk + validate ──────────────────────────────
            ctx = await self._stage(
                ctx, "chunk",
                lambda c: s07_chunk.chunk(c, self._chunker),
            )
            ctx = await self._stage(
                ctx, "validate_chunks",
                lambda c: s08_validate_chunks.validate_chunks(
                    c, min_chunk_length=self._min_chunk_length
                ),
            )
            if ctx.should_abort:
                span.set_attribute("rag.ingestion.aborted", True)
                await self._finalise(ctx)
                return ctx

            # ── Stage 9: embedding ────────────────────────────────────────
            ctx = await self._stage(
                ctx, "embed",
                lambda c: s09_embed.embed(c, self._embedder),
                is_async=True,
            )

            # ── Stage 10: RBAC ────────────────────────────────────────────
            ctx = await self._stage(
                ctx, "apply_rbac",
                lambda c: s10_rbac.apply_rbac(
                    c, reject_restricted=self._reject_restricted
                ),
            )
            if ctx.should_abort:
                span.set_attribute("rag.ingestion.aborted", True)
                await self._finalise(ctx)
                return ctx

            # ── Stages 11-12: persistence (hard) ─────────────────────────
            ctx = await self._stage(
                ctx, "upsert_vectors",
                lambda c: s11_vector_store.upsert_vectors(c, self._vector_store),
                is_async=True,
            )
            ctx = await self._stage(
                ctx, "upsert_document",
                lambda c: s12_doc_store.upsert_document(c, self._doc_store),
                is_async=True,
            )

            # ── Stage 13: graph (soft — supplementary store) ──────────────
            ctx = await self._stage(
                ctx, "upsert_graph",
                lambda c: s13_graph_store.upsert_graph(c, self._graph_store),
                is_async=True,
                soft=True,
            )

            # ── Stage 14: cache invalidation (soft) ───────────────────────
            ctx = await self._stage(
                ctx, "invalidate_cache",
                lambda c: s14_cache.invalidate_cache(c, self._cache),
                is_async=True,
                soft=True,
            )

            span.set_attribute(RAGAttributes.CHUNK_COUNT, len(ctx.chunks))

        # ── Stage 15: audit (always — outside span to guarantee execution) ─
        await self._finalise(ctx)
        return ctx

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _stage(
        self,
        ctx: IngestionContext,
        name: str,
        fn: Callable[[IngestionContext], Any],
        *,
        is_async: bool = False,
        soft: bool = False,
    ) -> IngestionContext:
        """Run one stage inside an OTel span; handle errors per soft/hard policy."""
        with record_span(
            f"ingestion.stage.{name}",
            **{RAGAttributes.INGESTION_STAGE: name},
        ) as span:
            try:
                if is_async:
                    ctx = await fn(ctx)
                else:
                    result = fn(ctx)
                    if asyncio.iscoroutine(result):
                        ctx = await result
                    else:
                        ctx = result
                ctx.mark_stage_done(name)
            except Exception as exc:
                ctx.stage_errors[name] = str(exc)
                span.set_attribute(RAGAttributes.ERROR_TYPE, type(exc).__name__)
                log.error("ingestion.stage_error", stage=name, error=str(exc))
                if not soft:
                    raise
        return ctx

    async def _finalise(self, ctx: IngestionContext) -> None:
        """Always run Stage 15 (audit), regardless of abort or prior errors."""
        with record_span(
            "ingestion.stage.audit",
            **{RAGAttributes.INGESTION_STAGE: "audit"},
        ):
            try:
                ctx = await s15_audit.emit_audit(ctx, self._audit)
                ctx.mark_stage_done("audit")
            except Exception as exc:
                log.error("ingestion.audit_failed", error=str(exc))
