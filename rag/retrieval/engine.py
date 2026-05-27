"""
RetrievalEngine — orchestrates the full retrieval pipeline for a single query.

Sequence:
  1. Embed the query (RETRIEVAL_QUERY task type for asymmetric embeddings)
  2. [Optional] Apply query transformations (step-back, multi-query, HyDE)
     — each variant is embedded and retrieved independently, then merged.
  3. Retrieve candidates via the configured strategy (dense / sparse / hybrid)
  4. [Optional] Apply MMR diversity re-ranking
  5. [Optional] Rerank with Cohere / cross-encoder
  6. Return final ordered list of RetrievalResult

RBAC:
  allowed_roles is passed through every retrieval call and enforced
  server-side in the vector store (AlloyDB pgvector RBAC filter).
  The engine cannot be called without supplying allowed_roles.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

from rag.core.schemas import (
    AugmentationConfig,
    HybridFusion,
    RAGConfig,
    RetrievalConfig,
    RetrievalStrategy,
)
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.retrieval.mmr import apply_mmr
from rag.retrieval.protocols import RetrievalResult, Retriever
from rag.retrieval.reranker import Reranker
from rag.retrieval.query_transform import apply_transformations

log = get_logger(__name__)

EmbedFn = Callable[[str], Awaitable[list[float]]]
GenerateFn = Callable[[str], Awaitable[str]]


def _deduplicate(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Remove duplicate chunk_ids, preserving the first (highest-ranked) occurrence."""
    seen: set[str] = set()
    out: list[RetrievalResult] = []
    for r in results:
        if r.chunk_id not in seen:
            seen.add(r.chunk_id)
            out.append(r)
    return out


def _reassign_ranks(results: list[RetrievalResult]) -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id=r.chunk_id,
            doc_id=r.doc_id,
            content=r.content,
            score=r.score,
            rank=i,
            retrieval_method=r.retrieval_method,
            metadata=r.metadata,
        )
        for i, r in enumerate(results)
    ]


class RetrievalEngine:
    """Orchestrates multi-strategy retrieval with optional reranking and MMR."""

    def __init__(
        self,
        config: RAGConfig,
        retriever: Retriever,
        embed_fn: EmbedFn,
        reranker: Reranker | None = None,
        generate_fn: GenerateFn | None = None,
    ) -> None:
        self._retrieval_cfg: RetrievalConfig = config.retrieval
        self._aug_cfg: AugmentationConfig = config.augmentation
        self._retriever = retriever
        self._embed_fn = embed_fn
        self._reranker = reranker
        self._generate_fn = generate_fn

    async def retrieve(
        self,
        query: str,
        *,
        allowed_roles: frozenset[str],
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Execute the full retrieval pipeline for a single query.

        Args:
            query:         Raw user query string.
            allowed_roles: RBAC roles of the requesting user.  Required.
            filters:       Optional server-side metadata filters.
            top_k:         Override the config top_k for this call.
        """
        effective_top_k = top_k if top_k is not None else self._retrieval_cfg.top_k

        with record_span(
            "retrieval.engine",
            **{
                RAGAttributes.RETRIEVAL_STRATEGY: self._retrieval_cfg.strategy.value,
                RAGAttributes.RETRIEVAL_TOP_K: effective_top_k,
            },
        ) as span:
            # ── 1. Query transformation ──────────────────────────────────────
            qt_cfg = self._aug_cfg.query_transformation
            if self._generate_fn and any([qt_cfg.step_back, qt_cfg.multi_query, qt_cfg.hyde]):
                query_variants = await apply_transformations(query, qt_cfg, self._generate_fn)
            else:
                query_variants = [query]

            # ── 2. Embed all query variants ──────────────────────────────────
            embeddings = await asyncio.gather(
                *(self._embed_fn(q) for q in query_variants)
            )

            # ── 3. Retrieve for each variant, then merge ─────────────────────
            all_results: list[RetrievalResult] = []
            retrieve_tasks = [
                self._retriever.retrieve(
                    emb,
                    q,
                    top_k=effective_top_k,
                    allowed_roles=allowed_roles,
                    filters=filters,
                )
                for q, emb in zip(query_variants, embeddings)
            ]
            batched = await asyncio.gather(*retrieve_tasks)
            for batch in batched:
                all_results.extend(batch)

            # Sort by score descending, dedup, keep top_k candidates.
            all_results.sort(key=lambda r: r.score, reverse=True)
            candidates = _deduplicate(all_results)[:effective_top_k]

            # ── 4. MMR diversity re-ranking ──────────────────────────────────
            mmr_cfg = self._retrieval_cfg.mmr
            if mmr_cfg.enabled and len(candidates) > 1:
                rerank_top_n = (
                    self._aug_cfg.reranker.top_n
                    if self._aug_cfg.reranker.enabled and self._reranker
                    else effective_top_k
                )
                candidates = apply_mmr(
                    candidates,
                    top_n=min(rerank_top_n, len(candidates)),
                    lambda_param=mmr_cfg.lambda_param,
                )

            # ── 5. Reranking ─────────────────────────────────────────────────
            if self._reranker and self._aug_cfg.reranker.enabled:
                candidates = await self._reranker.rerank(
                    query,
                    candidates,
                    top_n=self._aug_cfg.reranker.top_n,
                )

            results = _reassign_ranks(candidates)

            span.set_attribute(RAGAttributes.RETRIEVAL_CHUNK_COUNT, len(results))
            if results:
                span.set_attribute(RAGAttributes.RETRIEVAL_SCORE_MAX, results[0].score)
                span.set_attribute(RAGAttributes.RETRIEVAL_SCORE_MIN, results[-1].score)

            log.info(
                "retrieval.engine.complete",
                strategy=self._retrieval_cfg.strategy.value,
                query_variants=len(query_variants),
                returned=len(results),
            )
            return results
