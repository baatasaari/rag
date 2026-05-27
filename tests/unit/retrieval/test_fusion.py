"""
Tests for rag.retrieval.fusion — HybridRetriever with RRF / LINEAR fusion.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rag.core.schemas import (
    DenseRetrievalConfig,
    HybridFusion,
    RetrievalConfig,
    RetrievalStrategy,
    SparseProvider,
    SparseRetrievalConfig,
)
from rag.retrieval.fusion import HybridRetriever, _linear_fuse, _rrf_fuse
from rag.retrieval.protocols import RetrievalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(chunk_id: str, score: float, rank: int = 0, method: str = "dense") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=f"content for {chunk_id}",
        score=score,
        rank=rank,
        retrieval_method=method,
        metadata={},
    )


def _cfg(fusion: HybridFusion = HybridFusion.RRF, rrf_k: int = 60) -> RetrievalConfig:
    return RetrievalConfig(
        strategy=RetrievalStrategy.HYBRID,
        hybrid_fusion=fusion,
        rrf_k_constant=rrf_k,
        dense=DenseRetrievalConfig(weight=0.7),
        sparse=SparseRetrievalConfig(weight=0.3, provider=SparseProvider.BM25),
    )


def _make_hybrid(fusion=HybridFusion.RRF, dense_results=None, sparse_results=None):
    if dense_results is None:
        dense_results = [_result("c1", 0.9, 0), _result("c2", 0.7, 1)]
    if sparse_results is None:
        sparse_results = [_result("c2", 1.0, 0, "sparse"), _result("c3", 0.5, 1, "sparse")]

    dense_retriever = AsyncMock()
    dense_retriever.retrieve = AsyncMock(return_value=dense_results)
    sparse_retriever = AsyncMock()
    sparse_retriever.retrieve = AsyncMock(return_value=sparse_results)

    cfg = _cfg(fusion=fusion)
    return HybridRetriever(cfg, dense_retriever, sparse_retriever), dense_retriever, sparse_retriever


_EMBEDDING = [0.1, 0.2]
_ROLES = frozenset(["employee"])


# ── _rrf_fuse ─────────────────────────────────────────────────────────────────

class TestRRFFuse:
    def test_chunk_in_both_lists_scores_higher(self):
        dense = [_result("shared", 0.9, 0), _result("only_dense", 0.5, 1)]
        sparse = [_result("shared", 1.0, 0, "sparse"), _result("only_sparse", 0.3, 1, "sparse")]
        results = _rrf_fuse(dense, sparse, k=60, top_k=3)
        result_ids = [r.chunk_id for r in results]
        assert result_ids[0] == "shared"

    def test_top_k_limits_output(self):
        dense = [_result(f"d{i}", 1.0 - i * 0.1, i) for i in range(5)]
        sparse = [_result(f"s{i}", 1.0 - i * 0.1, i, "sparse") for i in range(5)]
        results = _rrf_fuse(dense, sparse, k=60, top_k=3)
        assert len(results) == 3

    def test_retrieval_method_is_hybrid(self):
        dense = [_result("c1", 0.9, 0)]
        sparse = [_result("c2", 0.8, 0, "sparse")]
        results = _rrf_fuse(dense, sparse, k=60, top_k=2)
        assert all(r.retrieval_method == "hybrid" for r in results)

    def test_rrf_score_formula(self):
        dense = [_result("c1", 0.9, 0)]
        sparse = [_result("c1", 0.9, 0, "sparse")]
        results = _rrf_fuse(dense, sparse, k=60, top_k=1)
        expected = 1 / (60 + 0) + 1 / (60 + 0)  # = 1/30
        assert abs(results[0].score - expected) < 1e-9

    def test_rank_reassigned_zero_based(self):
        dense = [_result("c1", 0.9, 5), _result("c2", 0.8, 6)]
        sparse = [_result("c3", 0.7, 0, "sparse")]
        results = _rrf_fuse(dense, sparse, k=60, top_k=3)
        assert results[0].rank == 0
        assert results[1].rank == 1


# ── _linear_fuse ──────────────────────────────────────────────────────────────

class TestLinearFuse:
    def test_combined_score_uses_weights(self):
        dense = [_result("c1", 1.0, 0)]
        sparse = [_result("c1", 1.0, 0, "sparse")]
        results = _linear_fuse(dense, sparse, dense_weight=0.7, sparse_weight=0.3, top_k=1)
        assert abs(results[0].score - 1.0) < 1e-9  # 0.7*1.0 + 0.3*1.0

    def test_only_dense_result(self):
        dense = [_result("c1", 0.8, 0)]
        sparse = []
        results = _linear_fuse(dense, sparse, dense_weight=0.7, sparse_weight=0.3, top_k=1)
        assert abs(results[0].score - 0.7 * 0.8) < 1e-9

    def test_top_k_limits_output(self):
        dense = [_result(f"c{i}", 1.0 - i * 0.1, i) for i in range(5)]
        sparse = []
        results = _linear_fuse(dense, sparse, dense_weight=0.7, sparse_weight=0.3, top_k=2)
        assert len(results) == 2

    def test_retrieval_method_is_hybrid(self):
        dense = [_result("c1", 0.9, 0)]
        sparse = [_result("c2", 0.8, 0, "sparse")]
        results = _linear_fuse(dense, sparse, dense_weight=0.7, sparse_weight=0.3, top_k=2)
        assert all(r.retrieval_method == "hybrid" for r in results)


# ── HybridRetriever ───────────────────────────────────────────────────────────

class TestHybridRetriever:
    @pytest.mark.asyncio
    async def test_calls_both_retrievers(self):
        hybrid, dense_r, sparse_r = _make_hybrid()
        await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES)
        dense_r.retrieve.assert_called_once()
        sparse_r.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_rrf_fusion_returns_results(self):
        hybrid, _, _ = _make_hybrid(fusion=HybridFusion.RRF)
        results = await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_linear_fusion_returns_results(self):
        hybrid, _, _ = _make_hybrid(fusion=HybridFusion.LINEAR)
        results = await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_allowed_roles_forwarded_to_both(self):
        hybrid, dense_r, sparse_r = _make_hybrid()
        roles = frozenset(["admin"])
        await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=roles)
        _, kwargs_d = dense_r.retrieve.call_args
        _, kwargs_s = sparse_r.retrieve.call_args
        assert kwargs_d["allowed_roles"] == roles
        assert kwargs_s["allowed_roles"] == roles

    @pytest.mark.asyncio
    async def test_chunk_appearing_in_both_ranked_first(self):
        dense = [_result("shared", 0.9, 0), _result("d_only", 0.5, 1)]
        sparse = [_result("shared", 1.0, 0, "sparse")]
        hybrid, _, _ = _make_hybrid(dense_results=dense, sparse_results=sparse)
        results = await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES)
        assert results[0].chunk_id == "shared"

    @pytest.mark.asyncio
    async def test_empty_results_from_both_returns_empty(self):
        hybrid, _, _ = _make_hybrid(dense_results=[], sparse_results=[])
        results = await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES)
        assert results == []

    @pytest.mark.asyncio
    async def test_filters_forwarded(self):
        hybrid, dense_r, sparse_r = _make_hybrid()
        filters = {"doc_type": "policy"}
        await hybrid.retrieve(_EMBEDDING, "q", top_k=5, allowed_roles=_ROLES, filters=filters)
        _, kwargs_d = dense_r.retrieve.call_args
        assert kwargs_d["filters"] == filters
