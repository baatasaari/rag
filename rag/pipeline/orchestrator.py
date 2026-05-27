"""
RAGPipeline — top-level query orchestrator.

Sequence for query():
  1. Start a root OTel span with query_id, user_id, and roles count.
  2. Embed the query (full-dimension for retrieval).
  3. Retrieve candidates via RetrievalEngine (RBAC enforced server-side).
  4. Compress retrieved chunks via ContextCompressor.
  5. Build Citation objects via CitationBuilder.
  6. Assemble AugmentedContext.
  7. Build the LLM prompt via PromptBuilder.
  8. Generate an answer via GenerationEngine (with semantic cache if wired).
  9. Wrap everything in a RAGResult and return.

stream_query() follows the same steps 1-7 then yields raw token strings
from GenerationEngine.stream().

Dependency injection:
  All heavy dependencies (adapters, engines, compressor, etc.) are injected
  at construction time.  Use the convenience factory ``RAGPipeline.build()``
  to wire them from a ``RAGConfig`` object.

RBAC invariant:
  allowed_roles from QueryContext is forwarded unchanged to RetrievalEngine,
  which passes it to the vector store's server-side filter.  The pipeline
  never widens or drops the role set.
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Callable, Awaitable

from rag.augmentation.citations import CitationBuilder
from rag.augmentation.compressor import ContextCompressor
from rag.augmentation.prompt_builder import PromptBuilder
from rag.augmentation.protocols import AugmentedContext
from rag.core.schemas import RAGConfig
from rag.generation.engine import GenerationEngine
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.pipeline.context import QueryContext
from rag.pipeline.result import RAGResult
from rag.retrieval.engine import RetrievalEngine
from rag.retrieval.protocols import RetrievalResult

log = get_logger(__name__)

EmbedFn = Callable[[str], Awaitable[list[float]]]


class RAGPipeline:
    """Orchestrates the full RAG query pipeline."""

    def __init__(
        self,
        config: RAGConfig,
        embed_fn: EmbedFn,
        retrieval_engine: RetrievalEngine,
        compressor: ContextCompressor,
        citation_builder: CitationBuilder,
        prompt_builder: PromptBuilder,
        generation_engine: GenerationEngine,
    ) -> None:
        self._config = config
        self._embed_fn = embed_fn
        self._retrieval = retrieval_engine
        self._compressor = compressor
        self._citations = citation_builder
        self._prompt_builder = prompt_builder
        self._generation = generation_engine

    # ── Public API ─────────────────────────────────────────────────────────────

    async def query(self, ctx: QueryContext) -> RAGResult:
        """Execute the full RAG pipeline and return a complete RAGResult."""
        with record_span(
            "pipeline.query",
            **{
                RAGAttributes.QUERY_ID: ctx.query_id,
                RAGAttributes.RETRIEVAL_STRATEGY: self._config.retrieval.strategy.value,
            },
        ) as span:
            t0 = time.monotonic()

            retrieval_results, augmented_ctx, prompt = await self._prepare(ctx)
            answer = await self._generation.generate(prompt)

            latency_ms = (time.monotonic() - t0) * 1000
            span.set_attribute(RAGAttributes.LATENCY_MS, round(latency_ms, 2))
            span.set_attribute(RAGAttributes.TOKENS_IN, answer.tokens_in)
            span.set_attribute(RAGAttributes.TOKENS_OUT, answer.tokens_out)
            span.set_attribute(RAGAttributes.CACHE_HIT, answer.cached)
            span.set_attribute(RAGAttributes.CITATION_COUNT, len(augmented_ctx.citations))

            result = RAGResult(
                query_id=ctx.query_id,
                query=ctx.query,
                answer=answer.answer,
                citations=augmented_ctx.citations,
                retrieval_results=retrieval_results,
                chunks_retrieved=len(retrieval_results),
                chunks_used=prompt.chunks_included,
                tokens_in=answer.tokens_in,
                tokens_out=answer.tokens_out,
                cached=answer.cached,
                provider=answer.provider,
                model=answer.model,
                latency_ms=latency_ms,
                citations_used=answer.citations_used,
            )
            log.info(
                "pipeline.query.complete",
                query_id=ctx.query_id,
                cached=answer.cached,
                chunks_retrieved=len(retrieval_results),
                chunks_used=prompt.chunks_included,
                tokens_in=answer.tokens_in,
                tokens_out=answer.tokens_out,
                latency_ms=round(latency_ms),
            )
            return result

    async def stream_query(self, ctx: QueryContext) -> AsyncIterator[str]:
        """Stream response tokens.  Performs retrieval and augmentation first."""
        retrieval_results, augmented_ctx, prompt = await self._prepare(ctx)
        async for token in self._generation.stream(prompt):
            yield token

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _prepare(
        self, ctx: QueryContext
    ) -> tuple[list[RetrievalResult], AugmentedContext, Any]:
        """Steps 1-7: embed → retrieve → compress → cite → augment → prompt."""
        # 1. Retrieve
        retrieval_results = await self._retrieval.retrieve(
            ctx.query,
            allowed_roles=ctx.allowed_roles,
            filters=ctx.filters,
            top_k=ctx.top_k,
        )

        # 2. Compress
        raw_chunks = [r.content for r in retrieval_results]
        compressed = await self._compressor.compress(ctx.query, raw_chunks)

        # 3. Build citations
        citations = self._citations.build(retrieval_results)

        # 4. Assemble AugmentedContext
        augmented_ctx = AugmentedContext(
            query=ctx.query,
            results=retrieval_results,
            compressed_chunks=compressed,
            citations=citations,
            total_chars=sum(len(c) for c in compressed),
        )

        # 5. Build prompt
        prompt = self._prompt_builder.build(augmented_ctx)

        return retrieval_results, augmented_ctx, prompt

    # ── Factory ────────────────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        config: RAGConfig,
        embed_fn: EmbedFn,
        retrieval_engine: RetrievalEngine,
        generation_engine: GenerationEngine,
        *,
        generate_fn: Callable[[str], Awaitable[str]] | None = None,
    ) -> "RAGPipeline":
        """Convenience factory — constructs augmentation components from config."""
        from rag.core.schemas import CitationMode

        gen_cfg = config.generation
        aug_cfg = config.augmentation

        compressor = ContextCompressor(
            aug_cfg.context_compression,
            generate_fn=generate_fn,
        )
        citation_builder = CitationBuilder(mode=gen_cfg.citation_mode)
        prompt_builder = PromptBuilder(
            system_template=gen_cfg.system_prompt_template,
        )
        return cls(
            config=config,
            embed_fn=embed_fn,
            retrieval_engine=retrieval_engine,
            compressor=compressor,
            citation_builder=citation_builder,
            prompt_builder=prompt_builder,
            generation_engine=generation_engine,
        )
