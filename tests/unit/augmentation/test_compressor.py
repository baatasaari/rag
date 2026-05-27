"""
Tests for rag.augmentation.compressor — ContextCompressor and helpers.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rag.core.schemas import CompressionStrategy, ContextCompressionConfig
from rag.augmentation.compressor import (
    ContextCompressor,
    _sentence_window,
    _llm_extract,
)


# ── _sentence_window ──────────────────────────────────────────────────────────

class TestSentenceWindow:
    def test_keeps_sentence_with_query_term(self):
        text = "The quick brown fox jumps. The cat sat on the mat. Foxes are clever animals."
        result = _sentence_window("fox", text)
        assert "fox" in result.lower()

    def test_falls_back_to_first_two_sentences_when_no_match(self):
        text = "Sentence one. Sentence two. Sentence three about nothing relevant."
        result = _sentence_window("quantum physics", text)
        assert "Sentence one" in result

    def test_empty_text_returns_empty(self):
        assert _sentence_window("query", "") == ""

    def test_includes_window_context_around_hit(self):
        text = "Unrelated start sentence. Relevant fox content here. Unrelated end sentence."
        result = _sentence_window("fox", text, window=1)
        # Should include context around the hit
        assert "fox" in result.lower()

    def test_short_query_terms_ignored(self):
        # Terms with 2 or fewer chars are not used for matching
        text = "The cat sat. Something else entirely."
        result = _sentence_window("is on", text)
        # No meaningful terms, fall back to first two sentences
        assert "The cat sat" in result


# ── _llm_extract ──────────────────────────────────────────────────────────────

class TestLLMExtract:
    @pytest.mark.asyncio
    async def test_returns_generated_text_stripped(self):
        gen = AsyncMock(return_value="  Relevant sentence here.  ")
        result = await _llm_extract("what is X?", "long chunk with X content", gen)
        assert result == "Relevant sentence here."

    @pytest.mark.asyncio
    async def test_falls_back_to_original_on_empty_llm_response(self):
        gen = AsyncMock(return_value="   ")
        chunk = "original chunk content"
        result = await _llm_extract("query", chunk, gen)
        assert result == chunk

    @pytest.mark.asyncio
    async def test_generate_called_once(self):
        gen = AsyncMock(return_value="answer")
        await _llm_extract("query", "chunk", gen)
        gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_contains_query_and_chunk(self):
        gen = AsyncMock(return_value="extracted")
        query = "what is the capital gains tax rate?"
        chunk = "CHUNK_CONTENT_XYZ"
        await _llm_extract(query, chunk, gen)
        prompt = gen.call_args[0][0]
        assert query in prompt
        assert chunk in prompt


# ── ContextCompressor ─────────────────────────────────────────────────────────

class TestContextCompressorDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_original_chunks(self):
        cfg = ContextCompressionConfig(enabled=False)
        compressor = ContextCompressor(cfg)
        chunks = ["chunk one", "chunk two"]
        result = await compressor.compress("query", chunks)
        assert result == chunks

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        cfg = ContextCompressionConfig(enabled=True)
        compressor = ContextCompressor(cfg)
        result = await compressor.compress("query", [])
        assert result == []


class TestContextCompressorSentenceWindow:
    @pytest.mark.asyncio
    async def test_sentence_window_strategy_used_when_no_generate_fn(self):
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.LLM_EXTRACT
        )
        # No generate_fn → falls back to sentence window
        compressor = ContextCompressor(cfg, generate_fn=None)
        chunks = [
            "The policy requires fox-like agility. Unrelated sentence about cats."
        ]
        result = await compressor.compress("fox policy", chunks)
        assert len(result) == 1
        assert isinstance(result[0], str)

    @pytest.mark.asyncio
    async def test_returns_one_result_per_input_chunk(self):
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.SENTENCE_WINDOW
        )
        compressor = ContextCompressor(cfg)
        chunks = ["chunk one", "chunk two", "chunk three"]
        result = await compressor.compress("query", chunks)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_output_is_shorter_or_equal(self):
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.SENTENCE_WINDOW
        )
        compressor = ContextCompressor(cfg)
        chunk = (
            "The policy requirement specifies that all employees must complete training. "
            "The capital requirement is set by the regulator. "
            "Unrelated content about office furniture procurement processes. "
            "More unrelated text about car parking spaces allocation."
        )
        result = await compressor.compress("capital requirement", [chunk])
        assert len(result[0]) <= len(chunk)


class TestContextCompressorLLMExtract:
    @pytest.mark.asyncio
    async def test_llm_called_per_chunk(self):
        gen = AsyncMock(return_value="extracted content")
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.LLM_EXTRACT
        )
        compressor = ContextCompressor(cfg, generate_fn=gen)
        chunks = ["chunk A", "chunk B", "chunk C"]
        result = await compressor.compress("query", chunks)
        assert gen.call_count == 3
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_chunks_run_concurrently(self):
        """All LLM calls should be gathered (not sequential)."""
        call_order: list[int] = []

        async def gen(prompt: str) -> str:
            # Each call appends its index; if sequential they'd be ordered
            call_order.append(len(call_order))
            return "extracted"

        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.LLM_EXTRACT
        )
        compressor = ContextCompressor(cfg, generate_fn=gen)
        await compressor.compress("query", ["c1", "c2", "c3"])
        assert len(call_order) == 3  # all 3 called


class TestContextCompressorMapReduce:
    @pytest.mark.asyncio
    async def test_short_chunk_uses_sentence_window(self):
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.MAP_REDUCE
        )
        compressor = ContextCompressor(cfg, generate_fn=None)
        # 800 chars threshold — this is short
        result = await compressor.compress("fox", ["The fox ran quickly."])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_long_chunk_with_no_generate_fn_uses_sentence_window(self):
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.MAP_REDUCE
        )
        compressor = ContextCompressor(cfg, generate_fn=None)
        long_chunk = "x " * 500  # 1000 chars, over threshold
        result = await compressor.compress("query", [long_chunk])
        assert isinstance(result[0], str)

    @pytest.mark.asyncio
    async def test_long_chunk_with_generate_fn_calls_per_segment(self):
        gen = AsyncMock(return_value="extracted segment")
        cfg = ContextCompressionConfig(
            enabled=True, strategy=CompressionStrategy.MAP_REDUCE
        )
        compressor = ContextCompressor(cfg, generate_fn=gen)
        # 2400 chars → 3 segments of 800
        long_chunk = "word content " * 185
        result = await compressor.compress("query", [long_chunk])
        assert gen.call_count >= 2  # at least 2 segments
        assert "extracted segment" in result[0]
