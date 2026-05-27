"""
Sparse Retriever — BM25 keyword search.

The retriever delegates to a `text_store` object that must expose:

    async def text_search(
        query: str,
        top_k: int,
        *,
        allowed_roles: frozenset[str] | None,
    ) -> list[SearchResult]

For AlloyDB this maps to a PostgreSQL FTS query (`to_tsvector` / `plainto_tsquery`).
For Vertex AI Search the concrete adapter calls the Discovery Engine API.

RBAC is forwarded to the text_store, which must enforce it server-side.
BM25 scoring is left to the backend; this layer normalises scores and converts
to RetrievalResult.
"""

from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable

from rag.core.schemas import SparseRetrievalConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.retrieval.protocols import RetrievalResult
from rag.storage.protocols import SearchResult

log = get_logger(__name__)


@runtime_checkable
class TextSearchable(Protocol):
    """Structural Protocol for any store that supports keyword / FTS search."""

    async def text_search(
        self,
        query: str,
        top_k: int,
        *,
        allowed_roles: frozenset[str] | None = None,
    ) -> list[SearchResult]: ...


def _normalise_score(score: float, max_score: float) -> float:
    """Normalise a BM25 / relevance score to [0, 1]."""
    if max_score <= 0:
        return 0.0
    return max(0.0, min(1.0, score / max_score))


class SparseRetriever:
    """Keyword retrieval delegating to a FTS-capable text_store."""

    def __init__(
        self,
        config: SparseRetrievalConfig,
        text_store: TextSearchable,
    ) -> None:
        self._config = config
        self._store = text_store

    async def retrieve(
        self,
        query_embedding: list[float],  # unused for sparse; kept for Protocol compatibility
        query_text: str,
        *,
        top_k: int,
        allowed_roles: frozenset[str],
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        with record_span(
            "retrieval.sparse",
            **{
                RAGAttributes.RETRIEVAL_TOP_K: top_k,
                RAGAttributes.RETRIEVAL_STRATEGY: "sparse",
            },
        ) as span:
            raw: list[SearchResult] = await self._store.text_search(
                query_text,
                top_k,
                allowed_roles=allowed_roles,
            )

            max_score = raw[0].score if raw else 1.0
            results = [
                RetrievalResult(
                    chunk_id=r.chunk_id,
                    doc_id=r.doc_id,
                    content=r.content,
                    score=_normalise_score(r.score, max_score),
                    rank=i,
                    retrieval_method="sparse",
                    metadata=r.metadata,
                )
                for i, r in enumerate(raw)
            ]

            span.set_attribute(RAGAttributes.RETRIEVAL_CHUNK_COUNT, len(results))
            log.info(
                "retrieval.sparse.complete",
                provider=self._config.provider.value,
                top_k=top_k,
                returned=len(results),
            )
            return results


# ── In-memory BM25 ────────────────────────────────────────────────────────────


class _BM25Index:
    """Minimal Okapi BM25 implementation for testing and small corpora.

    Parameters follow the standard BM25 defaults (k1=1.5, b=0.75).
    Not intended for production use at scale — use the AlloyDB FTS adapter.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._docs: list[tuple[str, list[str]]] = []  # (chunk_id, tokens)
        self._df: dict[str, int] = {}
        self._avg_dl: float = 0.0

    def index(self, chunk_id: str, text: str) -> None:
        tokens = text.lower().split()
        self._docs.append((chunk_id, tokens))
        for t in set(tokens):
            self._df[t] = self._df.get(t, 0) + 1
        total = sum(len(toks) for _, toks in self._docs)
        self._avg_dl = total / len(self._docs)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        q_terms = query.lower().split()
        N = len(self._docs)
        if N == 0:
            return []

        scores: list[tuple[str, float]] = []
        for chunk_id, tokens in self._docs:
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            dl = len(tokens)
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                df = self._df.get(term, 0)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
                tf_norm = (tf[term] * (self._k1 + 1)) / (
                    tf[term] + self._k1 * (1 - self._b + self._b * dl / self._avg_dl)
                )
                score += idf * tf_norm
            if score > 0:
                scores.append((chunk_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
