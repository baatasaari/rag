"""
Reranker — Cohere API with cross-encoder fallback.

Production path  (RerankerProvider.COHERE):
    Calls the Cohere rerank endpoint with the query and candidate passages.
    Requires config.api_key (SecretStr).  If the call fails, falls back to the
    cross-encoder provider if config.fallback_provider is set.

Cross-encoder path  (RerankerProvider.CROSS_ENCODER):
    Uses a lightweight TF-IDF overlap heuristic so the module imports without
    any ML framework dependency.  Replace the `_cross_encoder_score` function
    with a sentence-transformers model for production.

LLM path  (RerankerProvider.LLM):
    Stub — not implemented in this module.  The augmentation layer wires
    LLM-based reranking as a separate stage.

FCA compliance:
    Query text is sent to the Cohere API only after classification confirms the
    document is not RESTRICTED.  The ingestion pipeline enforces this before
    chunks reach the vector store; the retrieval layer does not re-check.
"""

from __future__ import annotations

import math
from typing import Any

from rag.core.schemas import RerankerConfig, RerankerProvider
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.retrieval.protocols import RetrievalResult

log = get_logger(__name__)


# ── Score helpers ─────────────────────────────────────────────────────────────


def _tfidf_overlap(query: str, passage: str) -> float:
    """Approximate relevance via normalised word overlap (TF proxy)."""
    q_terms = set(query.lower().split())
    p_terms = passage.lower().split()
    if not q_terms or not p_terms:
        return 0.0
    tf: dict[str, int] = {}
    for t in p_terms:
        tf[t] = tf.get(t, 0) + 1
    hits = sum(tf.get(t, 0) for t in q_terms)
    return hits / math.sqrt(len(p_terms))


def _cross_encoder_score(query: str, passage: str) -> float:
    """Cross-encoder heuristic (word-overlap TF score, normalised)."""
    raw = _tfidf_overlap(query, passage)
    return min(1.0, raw / 5.0)  # empirically caps near 1.0 for strong matches


# ── Cohere client (lazy import) ───────────────────────────────────────────────


async def _cohere_rerank(
    api_key: str,
    model: str,
    query: str,
    documents: list[str],
    top_n: int,
) -> list[tuple[int, float]]:
    """Call Cohere rerank API.  Returns (original_index, score) pairs."""
    try:
        import cohere  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "cohere package is required for RerankerProvider.COHERE — "
            "install it with: pip install cohere"
        ) from exc

    client = cohere.AsyncClientV2(api_key)
    response = await client.rerank(
        model=model,
        query=query,
        documents=documents,
        top_n=top_n,
    )
    return [(r.index, r.relevance_score) for r in response.results]


# ── Reranker ──────────────────────────────────────────────────────────────────


class Reranker:
    """Re-ranks retrieval candidates using Cohere or cross-encoder fallback."""

    def __init__(self, config: RerankerConfig) -> None:
        self._config = config

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        *,
        top_n: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Return the top_n best candidates, re-ranked by the configured provider."""
        if not self._config.enabled or not candidates:
            return candidates[: (top_n or self._config.top_n)]

        effective_top_n = top_n if top_n is not None else self._config.top_n

        with record_span(
            "retrieval.rerank",
            **{
                "rag.reranker.provider": self._config.provider.value,
                "rag.reranker.top_n": effective_top_n,
            },
        ) as span:
            try:
                results = await self._rerank_with(
                    self._config.provider,
                    query,
                    candidates,
                    effective_top_n,
                )
            except Exception as exc:
                log.warning(
                    "retrieval.rerank.primary_failed",
                    provider=self._config.provider.value,
                    error=str(exc),
                    fallback=self._config.fallback_provider.value
                    if self._config.fallback_provider
                    else None,
                )
                if self._config.fallback_provider is None:
                    raise
                results = await self._rerank_with(
                    self._config.fallback_provider,
                    query,
                    candidates,
                    effective_top_n,
                )

            span.set_attribute("rag.reranker.returned", len(results))
            log.info(
                "retrieval.rerank.complete",
                provider=self._config.provider.value,
                input_count=len(candidates),
                output_count=len(results),
            )
            return results

    async def _rerank_with(
        self,
        provider: RerankerProvider,
        query: str,
        candidates: list[RetrievalResult],
        top_n: int,
    ) -> list[RetrievalResult]:
        if provider == RerankerProvider.COHERE:
            if self._config.api_key is None:
                raise RuntimeError("RerankerConfig.api_key is required for Cohere reranking.")
            pairs = await _cohere_rerank(
                api_key=self._config.api_key.get_secret_value(),
                model=self._config.model,
                query=query,
                documents=[c.content for c in candidates],
                top_n=top_n,
            )
            ranked = sorted(pairs, key=lambda x: x[1], reverse=True)
            return [
                RetrievalResult(
                    chunk_id=candidates[idx].chunk_id,
                    doc_id=candidates[idx].doc_id,
                    content=candidates[idx].content,
                    score=score,
                    rank=new_rank,
                    retrieval_method=candidates[idx].retrieval_method,
                    metadata=candidates[idx].metadata,
                )
                for new_rank, (idx, score) in enumerate(ranked)
            ]

        if provider == RerankerProvider.CROSS_ENCODER:
            scored = [
                (i, _cross_encoder_score(query, c.content))
                for i, c in enumerate(candidates)
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [
                RetrievalResult(
                    chunk_id=candidates[i].chunk_id,
                    doc_id=candidates[i].doc_id,
                    content=candidates[i].content,
                    score=s,
                    rank=new_rank,
                    retrieval_method=candidates[i].retrieval_method,
                    metadata=candidates[i].metadata,
                )
                for new_rank, (i, s) in enumerate(scored[:top_n])
            ]

        raise NotImplementedError(f"RerankerProvider.{provider.value} not yet implemented.")
