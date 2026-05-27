"""
Dense Retriever — pgvector cosine similarity via AlloyDB.

RBAC is enforced server-side inside the vector store's SQL query
(`allowed_roles && $user_roles::text[]`).  The caller cannot bypass it.
"""

from __future__ import annotations

from typing import Any

from rag.core.schemas import DenseRetrievalConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.retrieval.protocols import RetrievalResult
from rag.storage.protocols import SearchResult, VectorStore

log = get_logger(__name__)


def _to_result(sr: SearchResult, rank: int) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=sr.chunk_id,
        doc_id=sr.doc_id,
        content=sr.content,
        score=max(0.0, min(1.0, (sr.score + 1.0) / 2.0)),  # [-1,1] → [0,1]
        rank=rank,
        retrieval_method="dense",
        metadata=sr.metadata,
    )


class DenseRetriever:
    """Retrieves candidates using embedding cosine similarity (pgvector)."""

    def __init__(self, config: DenseRetrievalConfig, vector_store: VectorStore) -> None:
        self._config = config
        self._store = vector_store

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
            "retrieval.dense",
            **{
                RAGAttributes.RETRIEVAL_TOP_K: top_k,
                RAGAttributes.RETRIEVAL_STRATEGY: "dense",
            },
        ) as span:
            raw: list[SearchResult] = await self._store.search(
                query_embedding,
                top_k,
                filters=filters,
                allowed_roles=allowed_roles,
            )
            results = [_to_result(r, i) for i, r in enumerate(raw)]

            span.set_attribute(RAGAttributes.RETRIEVAL_CHUNK_COUNT, len(results))
            if results:
                span.set_attribute(RAGAttributes.RETRIEVAL_SCORE_MAX, results[0].score)
                span.set_attribute(RAGAttributes.RETRIEVAL_SCORE_MIN, results[-1].score)

            log.info(
                "retrieval.dense.complete",
                top_k=top_k,
                returned=len(results),
            )
            return results
