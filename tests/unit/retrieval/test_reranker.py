"""
Tests for rag.retrieval.reranker — Reranker with cross-encoder and fallback.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pydantic import SecretStr

from rag.core.schemas import RerankerConfig, RerankerProvider
from rag.retrieval.protocols import RetrievalResult
from rag.retrieval.reranker import Reranker, _cross_encoder_score, _tfidf_overlap


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(chunk_id: str, score: float = 0.5, content: str = "sample content") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=content,
        score=score,
        rank=0,
        retrieval_method="dense",
        metadata={},
    )


def _cross_encoder_cfg(top_n: int = 3) -> RerankerConfig:
    return RerankerConfig(
        enabled=True,
        provider=RerankerProvider.CROSS_ENCODER,
        top_n=top_n,
        fallback_provider=None,
    )


# ── _tfidf_overlap ────────────────────────────────────────────────────────────

class TestTfidfOverlap:
    def test_no_overlap_returns_zero(self):
        assert _tfidf_overlap("quantum physics", "banana republic") == 0.0

    def test_full_overlap_positive(self):
        score = _tfidf_overlap("machine learning", "machine learning is great")
        assert score > 0

    def test_empty_query_returns_zero(self):
        assert _tfidf_overlap("", "some passage") == 0.0

    def test_empty_passage_returns_zero(self):
        assert _tfidf_overlap("query terms", "") == 0.0


# ── _cross_encoder_score ──────────────────────────────────────────────────────

class TestCrossEncoderScore:
    def test_returns_float_in_0_1(self):
        score = _cross_encoder_score("machine learning", "machine learning neural networks")
        assert 0.0 <= score <= 1.0

    def test_relevant_passage_scores_higher(self):
        query = "what is machine learning"
        relevant = "machine learning is a subset of artificial intelligence"
        irrelevant = "the weather is sunny and pleasant today"
        assert _cross_encoder_score(query, relevant) > _cross_encoder_score(query, irrelevant)


# ── Reranker (cross-encoder) ──────────────────────────────────────────────────

class TestRerankerCrossEncoder:
    @pytest.mark.asyncio
    async def test_returns_list_of_retrieval_results(self):
        cfg = _cross_encoder_cfg(top_n=2)
        reranker = Reranker(cfg)
        candidates = [_result("c1", 0.5, "machine learning content here"),
                      _result("c2", 0.4, "finance banking regulation compliance")]
        results = await reranker.rerank("machine learning", candidates, top_n=2)
        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_top_n_limits_output(self):
        cfg = _cross_encoder_cfg(top_n=2)
        reranker = Reranker(cfg)
        candidates = [_result(f"c{i}", 0.9 - i * 0.1, f"content {i}") for i in range(5)]
        results = await reranker.rerank("query", candidates, top_n=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_relevant_result_ranked_first(self):
        cfg = _cross_encoder_cfg(top_n=2)
        reranker = Reranker(cfg)
        candidates = [
            _result("c1", 0.3, "finance regulation compliance rules"),
            _result("c2", 0.2, "machine learning neural network python"),
        ]
        results = await reranker.rerank("machine learning", candidates)
        assert results[0].chunk_id == "c2"

    @pytest.mark.asyncio
    async def test_ranks_reassigned_zero_based(self):
        cfg = _cross_encoder_cfg(top_n=3)
        reranker = Reranker(cfg)
        candidates = [_result(f"c{i}", 0.5, "machine learning content") for i in range(3)]
        results = await reranker.rerank("machine learning", candidates)
        assert [r.rank for r in results] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_disabled_reranker_returns_candidates_sliced(self):
        cfg = RerankerConfig(
            enabled=False,
            provider=RerankerProvider.CROSS_ENCODER,
            top_n=2,
        )
        reranker = Reranker(cfg)
        candidates = [_result(f"c{i}", 0.5, "content") for i in range(5)]
        results = await reranker.rerank("query", candidates, top_n=2)
        assert len(results) == 2
        assert results[0].chunk_id == "c0"

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty(self):
        cfg = _cross_encoder_cfg()
        reranker = Reranker(cfg)
        results = await reranker.rerank("query", [])
        assert results == []


# ── Reranker (Cohere fallback) ────────────────────────────────────────────────

class TestRerankerFallback:
    @pytest.mark.asyncio
    async def test_cohere_failure_falls_back_to_cross_encoder(self):
        cfg = RerankerConfig(
            enabled=True,
            provider=RerankerProvider.COHERE,
            api_key=SecretStr("fake-key"),
            top_n=2,
            fallback_provider=RerankerProvider.CROSS_ENCODER,
        )
        reranker = Reranker(cfg)
        candidates = [_result("c1", 0.5, "machine learning text"), _result("c2", 0.4, "other")]
        # Cohere will raise RuntimeError (import error in test env) → falls back
        results = await reranker.rerank("machine learning", candidates, top_n=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_no_fallback_raises_on_primary_failure(self):
        cfg = RerankerConfig(
            enabled=True,
            provider=RerankerProvider.COHERE,
            api_key=SecretStr("fake-key"),
            top_n=2,
            fallback_provider=None,
        )
        reranker = Reranker(cfg)
        candidates = [_result("c1", 0.5, "text")]
        with pytest.raises(Exception):
            await reranker.rerank("query", candidates)
