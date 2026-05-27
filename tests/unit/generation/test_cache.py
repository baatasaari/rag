"""
Tests for rag.generation.cache — CachedGenerator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.generation.cache import CachedGenerator
from rag.generation.protocols import GeneratedAnswer
from rag.storage.protocols import CacheEntry


# ── helpers ───────────────────────────────────────────────────────────────────

def _cache_entry(response: str = "cached answer") -> CacheEntry:
    entry = MagicMock(spec=CacheEntry)
    entry.response = response
    return entry


def _answer(text: str = "fresh answer") -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=text,
        tokens_in=50,
        tokens_out=20,
        model="gemini",
        provider="vertex_ai",
    )


def _make_cached_gen(cache_hit: CacheEntry | None = None, adapter_answer: str = "fresh answer"):
    adapter = AsyncMock()
    adapter.model_name = "gemini"
    adapter.provider_name = "vertex_ai"
    adapter.generate = AsyncMock(return_value=_answer(adapter_answer))

    async def _fake_stream(system, user, **kw):
        for w in ["token1 ", "token2 ", "token3"]:
            yield w

    adapter.stream = MagicMock(return_value=_fake_stream("", ""))

    cache = AsyncMock()
    cache.get = AsyncMock(return_value=cache_hit)
    cache.set = AsyncMock()

    embed_fn = AsyncMock(return_value=[0.1, 0.2, 0.3])

    gen = CachedGenerator(adapter, cache, embed_fn, ttl_seconds=3600)
    return gen, adapter, cache, embed_fn


# ── generate — cache hit ──────────────────────────────────────────────────────

class TestCachedGeneratorHit:
    @pytest.mark.asyncio
    async def test_returns_cached_response(self):
        gen, adapter, _, _ = _make_cached_gen(cache_hit=_cache_entry("cached text"))
        result = await gen.generate("sys", "user msg")
        assert result.answer == "cached text"
        adapter.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_cached_flag_is_true(self):
        gen, _, _, _ = _make_cached_gen(cache_hit=_cache_entry())
        result = await gen.generate("sys", "user msg")
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_tokens_zero_on_cache_hit(self):
        gen, _, _, _ = _make_cached_gen(cache_hit=_cache_entry())
        result = await gen.generate("sys", "user msg")
        assert result.tokens_in == 0
        assert result.tokens_out == 0

    @pytest.mark.asyncio
    async def test_embed_fn_called_for_cache_lookup(self):
        gen, _, _, embed_fn = _make_cached_gen(cache_hit=_cache_entry())
        await gen.generate("sys", "user msg")
        embed_fn.assert_called_once()


# ── generate — cache miss ─────────────────────────────────────────────────────

class TestCachedGeneratorMiss:
    @pytest.mark.asyncio
    async def test_delegates_to_adapter_on_miss(self):
        gen, adapter, _, _ = _make_cached_gen(cache_hit=None, adapter_answer="fresh answer")
        result = await gen.generate("sys", "user msg")
        adapter.generate.assert_called_once()
        assert result.answer == "fresh answer"

    @pytest.mark.asyncio
    async def test_cached_flag_is_false_on_miss(self):
        gen, _, _, _ = _make_cached_gen(cache_hit=None)
        result = await gen.generate("sys", "user msg")
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_stores_response_in_cache(self):
        gen, _, cache, _ = _make_cached_gen(cache_hit=None)
        await gen.generate("sys", "user msg")
        cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_store_failure_does_not_raise(self):
        gen, _, cache, _ = _make_cached_gen(cache_hit=None)
        cache.set = AsyncMock(side_effect=RuntimeError("Redis down"))
        result = await gen.generate("sys", "user msg")
        assert result.answer == "fresh answer"  # still returns the answer

    @pytest.mark.asyncio
    async def test_custom_cache_key_text_used_for_embed(self):
        gen, _, _, embed_fn = _make_cached_gen(cache_hit=None)
        await gen.generate("sys", "user msg", cache_key_text="custom key")
        embed_fn.assert_called_once_with("custom key")

    @pytest.mark.asyncio
    async def test_ttl_passed_to_cache_set(self):
        gen, _, cache, _ = _make_cached_gen(cache_hit=None)
        await gen.generate("sys", "user msg")
        _, kwargs = cache.set.call_args
        assert kwargs["ttl_seconds"] == 3600


# ── stream ────────────────────────────────────────────────────────────────────

class TestCachedGeneratorStream:
    @pytest.mark.asyncio
    async def test_stream_hit_yields_words(self):
        gen, _, _, _ = _make_cached_gen(cache_hit=_cache_entry("hello world"))
        tokens = [t async for t in gen.stream("sys", "user")]
        # Cached response split by spaces and re-emitted
        full = "".join(tokens).strip()
        assert "hello" in full
        assert "world" in full

    @pytest.mark.asyncio
    async def test_stream_miss_yields_adapter_tokens(self):
        adapter = AsyncMock()
        adapter.model_name = "gemini"
        adapter.provider_name = "vertex_ai"

        async def _fake_stream(system, user, **kw):
            for w in ["tok1 ", "tok2"]:
                yield w

        adapter.stream = MagicMock(return_value=_fake_stream("", ""))

        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        embed_fn = AsyncMock(return_value=[0.1])

        gen = CachedGenerator(adapter, cache, embed_fn)
        tokens = [t async for t in gen.stream("sys", "user")]
        assert "tok1 " in tokens
        assert "tok2" in tokens

    @pytest.mark.asyncio
    async def test_stream_miss_caches_full_response(self):
        adapter = AsyncMock()
        adapter.model_name = "gemini"
        adapter.provider_name = "vertex_ai"

        async def _fake_stream(system, user, **kw):
            yield "hello "
            yield "world"

        adapter.stream = MagicMock(return_value=_fake_stream("", ""))

        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        embed_fn = AsyncMock(return_value=[0.1])

        gen = CachedGenerator(adapter, cache, embed_fn)
        _ = [t async for t in gen.stream("sys", "user")]

        cache.set.assert_called_once()
        _, kwargs = cache.set.call_args
        stored = cache.set.call_args[0][1]
        assert stored == "hello world"
