"""
Tests for rag.generation.engine — GenerationEngine.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.augmentation.prompt_builder import AssembledPrompt
from rag.generation.engine import GenerationEngine
from rag.generation.protocols import GeneratedAnswer


# ── helpers ───────────────────────────────────────────────────────────────────

def _prompt(query: str = "What is the policy?") -> AssembledPrompt:
    return AssembledPrompt(
        system="You are a helpful LBG assistant.",
        context_block="--- CONTEXT ---\n[1] Doc1\nContent here.\n--- END CONTEXT ---",
        sources_block="--- SOURCES ---\n[1] Doc1\n--- END SOURCES ---",
        user_message=f"Question: {query}\nAnswer:",
        total_chars=100,
        chunks_included=1,
        chunks_dropped=0,
    )


def _answer(text: str = "The policy requires [1] compliance.") -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=text,
        tokens_in=80,
        tokens_out=30,
        model="gemini",
        provider="vertex_ai",
    )


def _adapter(answer: GeneratedAnswer | None = None, raises: Exception | None = None):
    adapter = AsyncMock()
    adapter.provider_name = "vertex_ai"
    adapter.model_name = "gemini"
    if raises:
        adapter.generate = AsyncMock(side_effect=raises)
    else:
        adapter.generate = AsyncMock(return_value=answer or _answer())

    async def _stream(system, user, **kw):
        for w in ["token1 ", "token2"]:
            yield w

    adapter.stream = MagicMock(return_value=_stream("", ""))
    return adapter


# ── GenerationEngine.generate ─────────────────────────────────────────────────

class TestGenerationEngineGenerate:
    @pytest.mark.asyncio
    async def test_returns_generated_answer(self):
        engine = GenerationEngine(_adapter())
        result = await engine.generate(_prompt())
        assert isinstance(result, GeneratedAnswer)

    @pytest.mark.asyncio
    async def test_calls_primary_adapter(self):
        adapter = _adapter()
        engine = GenerationEngine(adapter)
        await engine.generate(_prompt())
        adapter.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_and_user_message_passed_correctly(self):
        adapter = _adapter()
        engine = GenerationEngine(adapter)
        prompt = _prompt("Tell me about capital requirements.")
        await engine.generate(prompt)
        call_args = adapter.generate.call_args
        assert call_args[0][0] == prompt.system
        assert call_args[0][1] == prompt.user_message

    @pytest.mark.asyncio
    async def test_temperature_forwarded(self):
        adapter = _adapter()
        engine = GenerationEngine(adapter, temperature=0.3)
        await engine.generate(_prompt())
        _, kwargs = adapter.generate.call_args
        assert kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_max_tokens_forwarded(self):
        adapter = _adapter()
        engine = GenerationEngine(adapter, max_tokens=1024)
        await engine.generate(_prompt())
        _, kwargs = adapter.generate.call_args
        assert kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_citations_extracted_from_answer(self):
        adapter = _adapter(answer=_answer("Policy [1] and regulation [3] apply."))
        engine = GenerationEngine(adapter)
        result = await engine.generate(_prompt())
        assert result.citations_used == [1, 3]


# ── Fallback ──────────────────────────────────────────────────────────────────

class TestGenerationEngineFallback:
    @pytest.mark.asyncio
    async def test_fallback_used_on_primary_failure(self):
        primary = _adapter(raises=RuntimeError("LLM unavailable"))
        fallback_answer = _answer("Fallback response [2].")
        fallback = _adapter(answer=fallback_answer)
        engine = GenerationEngine(primary, fallback=fallback)
        result = await engine.generate(_prompt())
        fallback.generate.assert_called_once()
        assert "Fallback response" in result.answer

    @pytest.mark.asyncio
    async def test_no_fallback_raises_on_primary_failure(self):
        primary = _adapter(raises=RuntimeError("LLM down"))
        engine = GenerationEngine(primary)
        with pytest.raises(RuntimeError, match="LLM down"):
            await engine.generate(_prompt())

    @pytest.mark.asyncio
    async def test_fallback_raises_propagates_original(self):
        primary = _adapter(raises=RuntimeError("primary down"))
        fallback = _adapter(raises=RuntimeError("fallback also down"))
        engine = GenerationEngine(primary, fallback=fallback)
        with pytest.raises(RuntimeError):
            await engine.generate(_prompt())

    @pytest.mark.asyncio
    async def test_fallback_not_called_when_primary_succeeds(self):
        primary = _adapter()
        fallback = _adapter()
        engine = GenerationEngine(primary, fallback=fallback)
        await engine.generate(_prompt())
        fallback.generate.assert_not_called()


# ── with_fallback ─────────────────────────────────────────────────────────────

class TestWithFallback:
    def test_returns_new_engine_instance(self):
        primary = _adapter()
        engine = GenerationEngine(primary)
        fallback = _adapter()
        new_engine = engine.with_fallback(fallback)
        assert new_engine is not engine
        assert new_engine._fallback is fallback

    def test_preserves_temperature_and_max_tokens(self):
        engine = GenerationEngine(_adapter(), temperature=0.5, max_tokens=512)
        new_engine = engine.with_fallback(_adapter())
        assert new_engine._temperature == 0.5
        assert new_engine._max_tokens == 512


# ── stream ────────────────────────────────────────────────────────────────────

class TestGenerationEngineStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        engine = GenerationEngine(_adapter())
        tokens = [t async for t in engine.stream(_prompt())]
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_stream_content_from_adapter(self):
        engine = GenerationEngine(_adapter())
        tokens = [t async for t in engine.stream(_prompt())]
        full = "".join(tokens)
        assert "token1" in full
        assert "token2" in full
