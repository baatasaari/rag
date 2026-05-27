"""
Hybrid Retriever — concurrent dense + sparse with RRF / LINEAR fusion.

Reciprocal Rank Fusion (RRF):
    score(d) = Σ  1 / (k + rank(d, list_i))
               i
where k=60 is the standard smoothing constant.

LINEAR fusion:
    score(d) = w_dense * dense_score(d) + w_sparse * sparse_score(d)
Weights must sum to 1.0 (enforced by RetrievalConfig validator).
"""

from __future__ import annotations

import asyncio
from typing import Any

from rag.core.schemas import HybridFusion, RetrievalConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.retrieval.protocols import RetrievalResult, Retriever

log = get_logger(__name__)


def _rrf_fuse(
    dense: list[RetrievalResult],
    sparse: list[RetrievalResult],
    k: int,
    top_k: int,
) -> list[RetrievalResult]:
    """Fuse two ranked lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}

    for rank, r in enumerate(dense):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (k + rank)

    for rank, r in enumerate(sparse):
        scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (k + rank)

    # Build a lookup for metadata from whichever list saw the chunk first.
    lookup: dict[str, RetrievalResult] = {}
    for r in (*dense, *sparse):
        if r.chunk_id not in lookup:
            lookup[r.chunk_id] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for new_rank, (chunk_id, score) in enumerate(ranked):
        base = lookup[chunk_id]
        results.append(
            RetrievalResult(
                chunk_id=base.chunk_id,
                doc_id=base.doc_id,
                content=base.content,
                score=score,
                rank=new_rank,
                retrieval_method="hybrid",
                metadata=base.metadata,
            )
        )
    return results


def _linear_fuse(
    dense: list[RetrievalResult],
    sparse: list[RetrievalResult],
    dense_weight: float,
    sparse_weight: float,
    top_k: int,
) -> list[RetrievalResult]:
    """Fuse two score lists with a weighted linear combination."""
    combined: dict[str, float] = {}
    lookup: dict[str, RetrievalResult] = {}

    for r in dense:
        combined[r.chunk_id] = combined.get(r.chunk_id, 0.0) + dense_weight * r.score
        lookup.setdefault(r.chunk_id, r)

    for r in sparse:
        combined[r.chunk_id] = combined.get(r.chunk_id, 0.0) + sparse_weight * r.score
        lookup.setdefault(r.chunk_id, r)

    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        RetrievalResult(
            chunk_id=lookup[cid].chunk_id,
            doc_id=lookup[cid].doc_id,
            content=lookup[cid].content,
            score=score,
            rank=i,
            retrieval_method="hybrid",
            metadata=lookup[cid].metadata,
        )
        for i, (cid, score) in enumerate(ranked)
    ]


class HybridRetriever:
    """Runs dense and sparse retrievers concurrently then fuses results."""

    def __init__(
        self,
        config: RetrievalConfig,
        dense_retriever: Retriever,
        sparse_retriever: Retriever,
    ) -> None:
        self._config = config
        self._dense = dense_retriever
        self._sparse = sparse_retriever

    async def retrieve(
        self,
        query_embedding: list[float],
        query_text: str,
        *,
        top_k: int,
        allowed_roles: frozenset[str],
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        with record_span(
            "retrieval.hybrid",
            **{
                RAGAttributes.RETRIEVAL_TOP_K: top_k,
                RAGAttributes.RETRIEVAL_STRATEGY: "hybrid",
            },
        ) as span:
            dense_results, sparse_results = await asyncio.gather(
                self._dense.retrieve(
                    query_embedding,
                    query_text,
                    top_k=top_k,
                    allowed_roles=allowed_roles,
                    filters=filters,
                ),
                self._sparse.retrieve(
                    query_embedding,
                    query_text,
                    top_k=top_k,
                    allowed_roles=allowed_roles,
                    filters=filters,
                ),
            )

            fusion = self._config.hybrid_fusion
            if fusion == HybridFusion.RRF:
                results = _rrf_fuse(
                    dense_results,
                    sparse_results,
                    k=self._config.rrf_k_constant,
                    top_k=top_k,
                )
            else:  # LINEAR or CASCADE falls back to LINEAR
                results = _linear_fuse(
                    dense_results,
                    sparse_results,
                    dense_weight=self._config.dense.weight,
                    sparse_weight=self._config.sparse.weight,
                    top_k=top_k,
                )

            span.set_attribute(RAGAttributes.RETRIEVAL_CHUNK_COUNT, len(results))
            log.info(
                "retrieval.hybrid.complete",
                fusion=fusion.value,
                dense_count=len(dense_results),
                sparse_count=len(sparse_results),
                fused_count=len(results),
            )
            return results
