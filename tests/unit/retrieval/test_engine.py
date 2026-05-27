"""
Tests for rag.retrieval.engine — RetrievalEngine orchestration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.core.schemas import (
    AugmentationConfig,
    DenseRetrievalConfig,
    HybridFusion,
    MMRConfig,
    QueryTransformationConfig,
    RAGConfig,
    RerankerConfig,
    RerankerProvider,
    RetrievalConfig,
    RetrievalStrategy,
    SparseProvider,
    SparseRetrievalConfig,
)
from rag.retrieval.engine import RetrievalEngine
from rag.retrieval.protocols import RetrievalResult
from rag.retrieval.reranker import Reranker


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(chunk_id: str, score: float, content: str = "content") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=content,
        score=score,
        rank=0,
        retrieval_method="dense",
        metadata={},
    )


def _make_config(
    *,
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
    top_k: int = 10,
    mmr_enabled: bool = False,
    reranker_enabled: bool = False,
    qt_step_back: bool = False,
    qt_multi_query: bool = False,
    qt_hyde: bool = False,
) -> RAGConfig:
    cfg = MagicMock(spec=RAGConfig)
    cfg.retrieval = RetrievalConfig(
        strategy=strategy,
        top_k=top_k,
        dense=DenseRetrievalConfig(weight=0.7),
        sparse=SparseRetrievalConfig(weight=0.3, provider=SparseProvider.BM25),
        hybrid_fusion=HybridFusion.RRF,
        mmr=MMRConfig(enabled=mmr_enabled),
    )
    cfg.augmentation = AugmentationConfig(
        reranker=RerankerConfig(
            enabled=reranker_enabled,
            provider=RerankerProvider.CROSS_ENCODER,
            top_n=3,
            fallback_provider=None,
        ),
        query_transformation=QueryTransformationConfig(
            step_back=qt_step_back,
            multi_query=qt_multi_query,
            hyde=qt_hyde,
        ),
    )
    return cfg


def _make_engine(
    retriever_results=None,
    *,
    mmr_enabled: bool = False,
    reranker_enabled: bool = False,
    with_reranker: bool = False,
    with_generate_fn: bool = False,
    top_k: int = 10,
):
    if retriever_results is None:
        retriever_results = [_result(f"c{i}", 0.9 - i * 0.05, f"content about topic {i}") for i in range(5)]

    cfg = _make_config(
        top_k=top_k,
        mmr_enabled=mmr_enabled,
        reranker_enabled=reranker_enabled,
    )

    retriever = AsyncMock()
    retriever.retrieve = AsyncMock(return_value=retriever_results)

    embed_fn = AsyncMock(return_value=[0.1, 0.2, 0.3])

    reranker = None
    if with_reranker:
        reranker = AsyncMock(spec=Reranker)
        reranker.rerank = AsyncMock(side_effect=lambda q, cands, **kw: cands[: kw.get("top_n", 3)])

    generate_fn = AsyncMock(return_value="generated") if with_generate_fn else None

    engine = RetrievalEngine(cfg, retriever, embed_fn, reranker, generate_fn)
    return engine, retriever, embed_fn


_ROLES = frozenset(["employee"])


# ── basic retrieval ───────────────────────────────────────────────────────────

class TestRetrievalEngineBasic:
    @pytest.mark.asyncio
    async def test_returns_list_of_retrieval_results(self):
        engine, _, _ = _make_engine()
        results = await engine.retrieve("what is the policy?", allowed_roles=_ROLES)
        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_retriever_called_with_embedding(self):
        engine, retriever, embed_fn = _make_engine()
        await engine.retrieve("query text", allowed_roles=_ROLES)
        embed_fn.assert_called_once_with("query text")
        retriever.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_allowed_roles_forwarded_to_retriever(self):
        engine, retriever, _ = _make_engine()
        roles = frozenset(["admin"])
        await engine.retrieve("q", allowed_roles=roles)
        _, kwargs = retriever.retrieve.call_args
        assert kwargs["allowed_roles"] == roles

    @pytest.mark.asyncio
    async def test_filters_forwarded_to_retriever(self):
        engine, retriever, _ = _make_engine()
        filters = {"category": "policy"}
        await engine.retrieve("q", allowed_roles=_ROLES, filters=filters)
        _, kwargs = retriever.retrieve.call_args
        assert kwargs["filters"] == filters

    @pytest.mark.asyncio
    async def test_top_k_override_used(self):
        engine, retriever, _ = _make_engine(top_k=20)
        await engine.retrieve("q", allowed_roles=_ROLES, top_k=5)
        _, kwargs = retriever.retrieve.call_args
        assert kwargs["top_k"] == 5

    @pytest.mark.asyncio
    async def test_ranks_reassigned_zero_based(self):
        engine, _, _ = _make_engine()
        results = await engine.retrieve("q", allowed_roles=_ROLES)
        assert [r.rank for r in results] == list(range(len(results)))

    @pytest.mark.asyncio
    async def test_empty_retriever_returns_empty(self):
        engine, _, _ = _make_engine(retriever_results=[])
        results = await engine.retrieve("q", allowed_roles=_ROLES)
        assert results == []


# ── deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:
    @pytest.mark.asyncio
    async def test_duplicate_chunk_ids_removed(self):
        dupes = [
            _result("c1", 0.9, "content A"),
            _result("c1", 0.85, "content A"),
            _result("c2", 0.7, "content B"),
        ]
        engine, retriever, _ = _make_engine(retriever_results=dupes)
        results = await engine.retrieve("q", allowed_roles=_ROLES)
        ids = [r.chunk_id for r in results]
        assert ids.count("c1") == 1


# ── MMR ───────────────────────────────────────────────────────────────────────

class TestMMR:
    @pytest.mark.asyncio
    async def test_mmr_applied_when_enabled(self):
        engine, _, _ = _make_engine(mmr_enabled=True, top_k=5)
        results = await engine.retrieve("q", allowed_roles=_ROLES)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_mmr_disabled_does_not_change_result_count(self):
        engine, _, _ = _make_engine(mmr_enabled=False)
        results = await engine.retrieve("q", allowed_roles=_ROLES)
        assert len(results) == 5  # all 5 test results returned


# ── Reranker ──────────────────────────────────────────────────────────────────

class TestEngineReranker:
    @pytest.mark.asyncio
    async def test_reranker_called_when_enabled(self):
        engine, _, _ = _make_engine(reranker_enabled=True, with_reranker=True)
        engine._reranker = AsyncMock()
        engine._reranker.rerank = AsyncMock(return_value=[_result("c0", 0.9, "best result")])
        await engine.retrieve("q", allowed_roles=_ROLES)
        engine._reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_reranker_object_skips_reranking(self):
        engine, retriever, _ = _make_engine(reranker_enabled=True, with_reranker=False)
        results = await engine.retrieve("q", allowed_roles=_ROLES)
        assert len(results) > 0


# ── Query transformation ──────────────────────────────────────────────────────

class TestQueryTransformation:
    @pytest.mark.asyncio
    async def test_no_generate_fn_uses_single_query(self):
        engine, retriever, embed_fn = _make_engine(with_generate_fn=False)
        await engine.retrieve("my query", allowed_roles=_ROLES)
        embed_fn.assert_called_once_with("my query")
        retriever.retrieve.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_fn_but_no_transforms_enabled_uses_single_query(self):
        engine, retriever, embed_fn = _make_engine(with_generate_fn=True)
        # No transforms enabled in default _make_config
        await engine.retrieve("my query", allowed_roles=_ROLES)
        embed_fn.assert_called_once_with("my query")
