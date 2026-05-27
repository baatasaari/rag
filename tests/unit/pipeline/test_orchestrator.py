"""
Tests for rag.pipeline.orchestrator — RAGPipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.augmentation.protocols import AugmentedContext, Citation
from rag.augmentation.prompt_builder import AssembledPrompt
from rag.core.schemas import CitationMode, RAGConfig
from rag.generation.protocols import GeneratedAnswer
from rag.pipeline.context import QueryContext
from rag.pipeline.orchestrator import RAGPipeline
from rag.pipeline.result import RAGResult
from rag.retrieval.protocols import RetrievalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _retrieval_result(chunk_id: str = "c1") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id, doc_id="doc1",
        content=f"Content of {chunk_id}",
        score=0.9, rank=0, retrieval_method="dense", metadata={},
    )


def _citation(idx: int = 1) -> Citation:
    return Citation(
        index=idx, chunk_id=f"c{idx}", doc_id=f"d{idx}",
        source_uri="gs://bucket/doc.pdf", title=f"Doc {idx}",
        page=None, mode=CitationMode.INLINE, snippet="snippet",
    )


def _generated_answer(text: str = "The policy requires [1] compliance.") -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=text, tokens_in=80, tokens_out=30,
        model="gemini", provider="vertex_ai",
    )


def _assembled_prompt() -> AssembledPrompt:
    return AssembledPrompt(
        system="sys", context_block="ctx", sources_block="src",
        user_message="q", total_chars=100, chunks_included=2, chunks_dropped=0,
    )


def _ctx(query: str = "What is the policy?") -> QueryContext:
    return QueryContext(
        query=query, user_id="user1",
        allowed_roles=frozenset(["employee"]),
    )


def _make_pipeline(
    retrieval_results: list[RetrievalResult] | None = None,
    answer: GeneratedAnswer | None = None,
):
    if retrieval_results is None:
        retrieval_results = [_retrieval_result("c1"), _retrieval_result("c2")]
    if answer is None:
        answer = _generated_answer()

    # RetrievalEngine mock
    retrieval_engine = AsyncMock()
    retrieval_engine.retrieve = AsyncMock(return_value=retrieval_results)

    # ContextCompressor mock
    compressor = AsyncMock()
    compressor.compress = AsyncMock(
        return_value=[f"compressed {r.content}" for r in retrieval_results]
    )

    # CitationBuilder mock
    citation_builder = MagicMock()
    citation_builder.build = MagicMock(
        return_value=[_citation(i + 1) for i in range(len(retrieval_results))]
    )

    # PromptBuilder mock
    prompt_builder = MagicMock()
    prompt_builder.build = MagicMock(return_value=_assembled_prompt())

    # GenerationEngine mock
    generation_engine = AsyncMock()
    generation_engine.generate = AsyncMock(return_value=answer)

    async def _fake_stream(prompt):
        for w in ["The ", "policy ", "requires [1]."]:
            yield w

    generation_engine.stream = MagicMock(return_value=_fake_stream(_assembled_prompt()))

    # Embed fn
    embed_fn = AsyncMock(return_value=[0.1, 0.2, 0.3])

    # Config
    config = RAGConfig()

    pipeline = RAGPipeline(
        config=config,
        embed_fn=embed_fn,
        retrieval_engine=retrieval_engine,
        compressor=compressor,
        citation_builder=citation_builder,
        prompt_builder=prompt_builder,
        generation_engine=generation_engine,
    )
    return pipeline, retrieval_engine, compressor, citation_builder, prompt_builder, generation_engine


_ROLES = frozenset(["employee"])


# ── RAGPipeline.query ─────────────────────────────────────────────────────────

class TestRAGPipelineQuery:
    @pytest.mark.asyncio
    async def test_returns_rag_result(self):
        pipeline, *_ = _make_pipeline()
        result = await pipeline.query(_ctx())
        assert isinstance(result, RAGResult)

    @pytest.mark.asyncio
    async def test_answer_populated(self):
        pipeline, *_ = _make_pipeline(answer=_generated_answer("Answer text [1]."))
        result = await pipeline.query(_ctx())
        assert result.answer == "Answer text [1]."

    @pytest.mark.asyncio
    async def test_query_id_preserved(self):
        pipeline, *_ = _make_pipeline()
        ctx = QueryContext(query="q", user_id="u", allowed_roles=_ROLES, query_id="fixed-id")
        result = await pipeline.query(ctx)
        assert result.query_id == "fixed-id"

    @pytest.mark.asyncio
    async def test_retrieval_called_with_correct_roles(self):
        pipeline, retrieval_engine, *_ = _make_pipeline()
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset(["admin"]))
        await pipeline.query(ctx)
        _, kwargs = retrieval_engine.retrieve.call_args
        assert kwargs["allowed_roles"] == frozenset(["admin"])

    @pytest.mark.asyncio
    async def test_filters_forwarded_to_retrieval(self):
        pipeline, retrieval_engine, *_ = _make_pipeline()
        ctx = QueryContext(
            query="q", user_id="u", allowed_roles=_ROLES,
            filters={"doc_type": "policy"},
        )
        await pipeline.query(ctx)
        _, kwargs = retrieval_engine.retrieve.call_args
        assert kwargs["filters"] == {"doc_type": "policy"}

    @pytest.mark.asyncio
    async def test_top_k_override_forwarded(self):
        pipeline, retrieval_engine, *_ = _make_pipeline()
        ctx = QueryContext(query="q", user_id="u", allowed_roles=_ROLES, top_k=3)
        await pipeline.query(ctx)
        _, kwargs = retrieval_engine.retrieve.call_args
        assert kwargs["top_k"] == 3

    @pytest.mark.asyncio
    async def test_chunks_retrieved_equals_retrieval_results_count(self):
        results = [_retrieval_result(f"c{i}") for i in range(4)]
        pipeline, *_ = _make_pipeline(retrieval_results=results)
        result = await pipeline.query(_ctx())
        assert result.chunks_retrieved == 4

    @pytest.mark.asyncio
    async def test_chunks_used_from_prompt(self):
        pipeline, *_ = _make_pipeline()
        result = await pipeline.query(_ctx())
        assert result.chunks_used == 2  # from _assembled_prompt().chunks_included

    @pytest.mark.asyncio
    async def test_token_counts_from_answer(self):
        pipeline, *_ = _make_pipeline(answer=_generated_answer())
        result = await pipeline.query(_ctx())
        assert result.tokens_in == 80
        assert result.tokens_out == 30

    @pytest.mark.asyncio
    async def test_cached_flag_from_answer(self):
        ans = GeneratedAnswer(
            answer="cached", tokens_in=0, tokens_out=0,
            model="g", provider="vertex_ai", cached=True,
        )
        pipeline, *_ = _make_pipeline(answer=ans)
        result = await pipeline.query(_ctx())
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_latency_ms_is_positive_float(self):
        pipeline, *_ = _make_pipeline()
        result = await pipeline.query(_ctx())
        assert isinstance(result.latency_ms, float)
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_citations_built_from_retrieval_results(self):
        results = [_retrieval_result(f"c{i}") for i in range(3)]
        pipeline, _, _, citation_builder, *_ = _make_pipeline(retrieval_results=results)
        await pipeline.query(_ctx())
        citation_builder.build.assert_called_once_with(results)

    @pytest.mark.asyncio
    async def test_compression_called_with_query_and_chunk_texts(self):
        results = [_retrieval_result("c1"), _retrieval_result("c2")]
        pipeline, _, compressor, *_ = _make_pipeline(retrieval_results=results)
        ctx = _ctx("What is the capital requirement?")
        await pipeline.query(ctx)
        compressor.compress.assert_called_once_with(
            "What is the capital requirement?",
            [r.content for r in results],
        )

    @pytest.mark.asyncio
    async def test_generation_called_with_prompt(self):
        pipeline, _, _, _, prompt_builder, generation_engine = _make_pipeline()
        await pipeline.query(_ctx())
        generation_engine.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_retrieval_produces_valid_result(self):
        pipeline, *_ = _make_pipeline(retrieval_results=[])
        result = await pipeline.query(_ctx())
        assert result.chunks_retrieved == 0
        assert isinstance(result.answer, str)

    @pytest.mark.asyncio
    async def test_citations_used_extracted_from_answer(self):
        ans = _generated_answer("Policy [1] and regulation [3] apply.")
        pipeline, *_ = _make_pipeline(answer=ans)
        result = await pipeline.query(_ctx())
        assert 1 in result.citations_used
        assert 3 in result.citations_used


# ── RAGPipeline.stream_query ──────────────────────────────────────────────────

class TestRAGPipelineStreamQuery:
    @pytest.mark.asyncio
    async def test_yields_string_tokens(self):
        pipeline, *_ = _make_pipeline()
        tokens = [t async for t in pipeline.stream_query(_ctx())]
        assert all(isinstance(t, str) for t in tokens)

    @pytest.mark.asyncio
    async def test_yields_multiple_tokens(self):
        pipeline, *_ = _make_pipeline()
        tokens = [t async for t in pipeline.stream_query(_ctx())]
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_retrieval_called_before_streaming(self):
        pipeline, retrieval_engine, *_ = _make_pipeline()
        _ = [t async for t in pipeline.stream_query(_ctx())]
        retrieval_engine.retrieve.assert_called_once()


# ── RAGPipeline.build factory ─────────────────────────────────────────────────

class TestRAGPipelineBuild:
    def test_build_returns_pipeline_instance(self):
        config = RAGConfig()
        embed_fn = AsyncMock(return_value=[0.1])
        retrieval_engine = AsyncMock()
        generation_engine = AsyncMock()

        pipeline = RAGPipeline.build(
            config, embed_fn, retrieval_engine, generation_engine
        )
        assert isinstance(pipeline, RAGPipeline)

    def test_build_wires_citation_mode_from_config(self):
        config = RAGConfig()
        embed_fn = AsyncMock(return_value=[0.1])
        retrieval_engine = AsyncMock()
        generation_engine = AsyncMock()

        pipeline = RAGPipeline.build(
            config, embed_fn, retrieval_engine, generation_engine
        )
        # CitationMode from config.generation.citation_mode (default INLINE)
        assert pipeline._citations._mode == config.generation.citation_mode

    def test_build_with_generate_fn(self):
        config = RAGConfig()
        embed_fn = AsyncMock(return_value=[0.1])
        retrieval_engine = AsyncMock()
        generation_engine = AsyncMock()
        generate_fn = AsyncMock(return_value="generated")

        pipeline = RAGPipeline.build(
            config, embed_fn, retrieval_engine, generation_engine,
            generate_fn=generate_fn,
        )
        assert pipeline._compressor._generate_fn is generate_fn
