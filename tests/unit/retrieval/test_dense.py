"""
Tests for rag.retrieval.dense — DenseRetriever.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.core.schemas import DenseRetrievalConfig, DataClassificationLevel
from rag.retrieval.dense import DenseRetriever, _to_result
from rag.retrieval.protocols import RetrievalResult
from rag.storage.protocols import SearchResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _sr(chunk_id: str = "c1", score: float = 0.8) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content="sample content",
        score=score,
        metadata={"source": "test"},
        classification_level=DataClassificationLevel.INTERNAL,
        allowed_roles=frozenset(["employee"]),
    )


def _make_retriever(search_return=None):
    if search_return is None:
        search_return = [_sr()]
    vector_store = AsyncMock()
    vector_store.search = AsyncMock(return_value=search_return)
    config = DenseRetrievalConfig()
    return DenseRetriever(config, vector_store), vector_store


_EMBEDDING = [0.1, 0.2, 0.3]
_ROLES = frozenset(["employee"])


# ── _to_result ────────────────────────────────────────────────────────────────

class TestToResult:
    def test_score_normalised_from_cosine(self):
        sr = _sr(score=0.6)
        r = _to_result(sr, 0)
        # (0.6 + 1.0) / 2.0 = 0.8
        assert abs(r.score - 0.8) < 1e-6

    def test_score_clamped_low(self):
        sr = _sr(score=-1.0)
        r = _to_result(sr, 0)
        assert r.score == 0.0

    def test_score_clamped_high(self):
        sr = _sr(score=1.0)
        r = _to_result(sr, 0)
        assert r.score == 1.0

    def test_retrieval_method_is_dense(self):
        r = _to_result(_sr(), 0)
        assert r.retrieval_method == "dense"

    def test_rank_set_correctly(self):
        r = _to_result(_sr(), 5)
        assert r.rank == 5

    def test_metadata_preserved(self):
        sr = _sr()
        r = _to_result(sr, 0)
        assert r.metadata == {"source": "test"}


# ── DenseRetriever.retrieve ───────────────────────────────────────────────────

class TestDenseRetriever:
    @pytest.mark.asyncio
    async def test_returns_list_of_retrieval_results(self):
        retriever, _ = _make_retriever()
        results = await retriever.retrieve(_EMBEDDING, "query", top_k=5, allowed_roles=_ROLES)
        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_vector_store_called_with_allowed_roles(self):
        retriever, vs = _make_retriever()
        await retriever.retrieve(_EMBEDDING, "query", top_k=5, allowed_roles=_ROLES)
        vs.search.assert_called_once_with(
            _EMBEDDING,
            5,
            filters=None,
            allowed_roles=_ROLES,
        )

    @pytest.mark.asyncio
    async def test_filters_forwarded(self):
        retriever, vs = _make_retriever()
        filters = {"doc_type": "policy"}
        await retriever.retrieve(_EMBEDDING, "q", top_k=3, allowed_roles=_ROLES, filters=filters)
        _, kwargs = vs.search.call_args
        assert kwargs["filters"] == filters

    @pytest.mark.asyncio
    async def test_empty_store_returns_empty(self):
        retriever, _ = _make_retriever(search_return=[])
        results = await retriever.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES)
        assert results == []

    @pytest.mark.asyncio
    async def test_rank_is_sequential(self):
        srs = [_sr(f"c{i}", 0.9 - i * 0.1) for i in range(3)]
        retriever, _ = _make_retriever(search_return=srs)
        results = await retriever.retrieve(_EMBEDDING, "q", top_k=3, allowed_roles=_ROLES)
        assert [r.rank for r in results] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_multiple_results_ordered_by_store(self):
        srs = [_sr("c1", 0.9), _sr("c2", 0.5)]
        retriever, _ = _make_retriever(search_return=srs)
        results = await retriever.retrieve(_EMBEDDING, "q", top_k=2, allowed_roles=_ROLES)
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c2"
