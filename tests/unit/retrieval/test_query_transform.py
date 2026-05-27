"""
Tests for rag.retrieval.query_transform — query transformation helpers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rag.core.schemas import QueryTransformationConfig
from rag.retrieval.query_transform import (
    apply_transformations,
    hyde,
    multi_query,
    step_back,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _generate(response: str) -> AsyncMock:
    fn = AsyncMock(return_value=response)
    return fn


# ── step_back ─────────────────────────────────────────────────────────────────

class TestStepBack:
    @pytest.mark.asyncio
    async def test_returns_stripped_string(self):
        gen = _generate("  What are common regulatory frameworks?  ")
        result = await step_back("What is FCA rule 9.1.2?", gen)
        assert result == "What are common regulatory frameworks?"

    @pytest.mark.asyncio
    async def test_generate_called_once(self):
        gen = _generate("broader question")
        await step_back("specific question", gen)
        gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_contains_original_query(self):
        gen = _generate("result")
        original = "What is the capital gains tax rate?"
        await step_back(original, gen)
        prompt = gen.call_args[0][0]
        assert original in prompt


# ── multi_query ───────────────────────────────────────────────────────────────

class TestMultiQuery:
    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self):
        gen = _generate("query one\nquery two\nquery three")
        results = await multi_query("original", gen, count=3)
        assert isinstance(results, list)
        assert all(isinstance(q, str) for q in results)

    @pytest.mark.asyncio
    async def test_count_limits_output(self):
        gen = _generate("line1\nline2\nline3\nline4\nline5")
        results = await multi_query("q", gen, count=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_empty_lines_filtered(self):
        gen = _generate("line1\n\nline2\n")
        results = await multi_query("q", gen, count=3)
        assert "" not in results


# ── hyde ──────────────────────────────────────────────────────────────────────

class TestHyDE:
    @pytest.mark.asyncio
    async def test_returns_stripped_string(self):
        gen = _generate("  A hypothetical answer.  ")
        result = await hyde("What is FCA?", gen)
        assert result == "A hypothetical answer."

    @pytest.mark.asyncio
    async def test_generate_called_once(self):
        gen = _generate("answer")
        await hyde("question", gen)
        gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_contains_query(self):
        gen = _generate("result")
        query = "What are LBG's capital requirements?"
        await hyde(query, gen)
        prompt = gen.call_args[0][0]
        assert query in prompt


# ── apply_transformations ─────────────────────────────────────────────────────

class TestApplyTransformations:
    @pytest.mark.asyncio
    async def test_original_query_always_first(self):
        cfg = QueryTransformationConfig(step_back=False, multi_query=False, hyde=False)
        gen = AsyncMock()
        results = await apply_transformations("my query", cfg, gen)
        assert results[0] == "my query"

    @pytest.mark.asyncio
    async def test_no_transforms_returns_just_original(self):
        cfg = QueryTransformationConfig(step_back=False, multi_query=False, hyde=False)
        gen = AsyncMock()
        results = await apply_transformations("my query", cfg, gen)
        assert results == ["my query"]

    @pytest.mark.asyncio
    async def test_step_back_adds_query(self):
        cfg = QueryTransformationConfig(step_back=True, multi_query=False, hyde=False)
        gen = AsyncMock(return_value="broader question")
        results = await apply_transformations("specific", cfg, gen)
        assert "broader question" in results
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_multi_query_adds_queries(self):
        cfg = QueryTransformationConfig(
            step_back=False, multi_query=True, hyde=False, multi_query_count=2
        )
        gen = AsyncMock(return_value="variant one\nvariant two")
        results = await apply_transformations("original", cfg, gen)
        assert "variant one" in results
        assert "variant two" in results

    @pytest.mark.asyncio
    async def test_no_duplicate_queries(self):
        cfg = QueryTransformationConfig(step_back=True, multi_query=False, hyde=False)
        gen = AsyncMock(return_value="original")  # step_back returns same as input
        results = await apply_transformations("original", cfg, gen)
        assert results.count("original") == 1

    @pytest.mark.asyncio
    async def test_transform_failure_does_not_raise(self):
        cfg = QueryTransformationConfig(step_back=True, multi_query=False, hyde=False)
        gen = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        results = await apply_transformations("my query", cfg, gen)
        # Should degrade gracefully, returning at least the original
        assert "my query" in results

    @pytest.mark.asyncio
    async def test_hyde_adds_hypothetical_document(self):
        cfg = QueryTransformationConfig(step_back=False, multi_query=False, hyde=True)
        gen = AsyncMock(return_value="A hypothetical document about the topic.")
        results = await apply_transformations("what is X?", cfg, gen)
        assert "A hypothetical document about the topic." in results
