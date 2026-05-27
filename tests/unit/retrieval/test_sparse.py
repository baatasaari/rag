"""
Tests for rag.retrieval.sparse — SparseRetriever and _BM25Index.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rag.core.schemas import SparseProvider, SparseRetrievalConfig, DataClassificationLevel
from rag.retrieval.protocols import RetrievalResult
from rag.retrieval.sparse import SparseRetriever, _BM25Index, _normalise_score
from rag.storage.protocols import SearchResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _sr(chunk_id: str, score: float, content: str = "sample text") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=content,
        score=score,
        metadata={},
        classification_level=DataClassificationLevel.INTERNAL,
        allowed_roles=frozenset(["employee"]),
    )


def _make_retriever(search_return=None):
    if search_return is None:
        search_return = [_sr("c1", 3.5)]
    text_store = AsyncMock()
    text_store.text_search = AsyncMock(return_value=search_return)
    config = SparseRetrievalConfig(provider=SparseProvider.BM25)
    return SparseRetriever(config, text_store), text_store


_ROLES = frozenset(["employee"])
_EMB = [0.1, 0.2]


# ── normalise_score ───────────────────────────────────────────────────────────

class TestNormaliseScore:
    def test_zero_max_returns_zero(self):
        assert _normalise_score(5.0, 0.0) == 0.0

    def test_same_score_as_max_returns_one(self):
        assert _normalise_score(4.0, 4.0) == 1.0

    def test_half_max_returns_half(self):
        assert abs(_normalise_score(2.0, 4.0) - 0.5) < 1e-9

    def test_clamped_above_one(self):
        assert _normalise_score(10.0, 5.0) == 1.0

    def test_negative_clamped_to_zero(self):
        assert _normalise_score(-1.0, 4.0) == 0.0


# ── SparseRetriever ───────────────────────────────────────────────────────────

class TestSparseRetriever:
    @pytest.mark.asyncio
    async def test_returns_retrieval_results(self):
        retriever, _ = _make_retriever()
        results = await retriever.retrieve(_EMB, "keyword query", top_k=5, allowed_roles=_ROLES)
        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_retrieval_method_is_sparse(self):
        retriever, _ = _make_retriever()
        results = await retriever.retrieve(_EMB, "q", top_k=5, allowed_roles=_ROLES)
        assert all(r.retrieval_method == "sparse" for r in results)

    @pytest.mark.asyncio
    async def test_text_store_called_with_query_and_roles(self):
        retriever, ts = _make_retriever()
        await retriever.retrieve(_EMB, "my query", top_k=3, allowed_roles=_ROLES)
        ts.text_search.assert_called_once_with("my query", 3, allowed_roles=_ROLES)

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty(self):
        retriever, _ = _make_retriever(search_return=[])
        results = await retriever.retrieve(_EMB, "q", top_k=5, allowed_roles=_ROLES)
        assert results == []

    @pytest.mark.asyncio
    async def test_scores_normalised_to_0_1(self):
        srs = [_sr("c1", 10.0), _sr("c2", 5.0), _sr("c3", 2.0)]
        retriever, _ = _make_retriever(search_return=srs)
        results = await retriever.retrieve(_EMB, "q", top_k=3, allowed_roles=_ROLES)
        assert all(0.0 <= r.score <= 1.0 for r in results)

    @pytest.mark.asyncio
    async def test_first_result_score_is_one(self):
        srs = [_sr("c1", 8.0), _sr("c2", 4.0)]
        retriever, _ = _make_retriever(search_return=srs)
        results = await retriever.retrieve(_EMB, "q", top_k=2, allowed_roles=_ROLES)
        assert results[0].score == 1.0

    @pytest.mark.asyncio
    async def test_rank_assigned_sequentially(self):
        srs = [_sr(f"c{i}", float(5 - i)) for i in range(3)]
        retriever, _ = _make_retriever(search_return=srs)
        results = await retriever.retrieve(_EMB, "q", top_k=3, allowed_roles=_ROLES)
        assert [r.rank for r in results] == [0, 1, 2]


# ── _BM25Index ────────────────────────────────────────────────────────────────

class TestBM25Index:
    def test_empty_index_returns_empty(self):
        idx = _BM25Index()
        assert idx.search("hello", top_k=5) == []

    def test_exact_match_scores_higher_than_no_match(self):
        idx = _BM25Index()
        idx.index("c1", "the quick brown fox jumps over the lazy dog")
        idx.index("c2", "some completely unrelated content about finance")
        results = idx.search("fox jumps", top_k=2)
        assert results[0][0] == "c1"

    def test_top_k_limits_results(self):
        idx = _BM25Index()
        for i in range(10):
            idx.index(f"c{i}", f"keyword document number {i} with extra content here")
        results = idx.search("keyword document", top_k=3)
        assert len(results) <= 3

    def test_no_query_match_returns_empty(self):
        idx = _BM25Index()
        idx.index("c1", "the quick brown fox")
        results = idx.search("completely absent term xyz", top_k=5)
        assert results == []

    def test_scores_are_positive_floats(self):
        idx = _BM25Index()
        idx.index("c1", "machine learning neural network deep learning")
        results = idx.search("machine learning", top_k=1)
        assert results[0][1] > 0

    def test_more_term_matches_score_higher(self):
        idx = _BM25Index()
        idx.index("c_many", "python python python code python script")
        idx.index("c_few", "python javascript ruby code")
        results = dict(idx.search("python", top_k=2))
        assert results["c_many"] > results["c_few"]
