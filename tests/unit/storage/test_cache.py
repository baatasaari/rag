"""
Tests for rag.storage.cache — Redis semantic cache.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.core.schemas import CacheConfig, SemanticCacheConfig
from rag.storage.cache import (
    RedisSemanticCache,
    _cosine_similarity,
    _embedding_fingerprint,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_config(*, enabled: bool = True, threshold: float = 0.97) -> CacheConfig:
    return CacheConfig(
        semantic_cache=SemanticCacheConfig(enabled=enabled, threshold=threshold, dimensions=64),
        ttl_seconds=3600,
        key_prefix="test",
    )


def _make_pipeline() -> MagicMock:
    pipe = MagicMock()
    pipe.set = MagicMock(return_value=pipe)
    pipe.hset = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[True, True, True, True])
    return pipe


def _make_redis(*, scan_keys: list | None = None) -> AsyncMock:
    """Return a mock aioredis client."""
    redis = AsyncMock()
    _keys = scan_keys or []

    async def _scan_iter(*args, **kwargs):
        for key in _keys:
            yield key

    redis.scan_iter = _scan_iter
    redis.pipeline = MagicMock(return_value=_make_pipeline())
    redis.hgetall = AsyncMock(return_value={})
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()
    return redis


# ── _embedding_fingerprint() ──────────────────────────────────────────────────


class TestEmbeddingFingerprint:
    def test_returns_16_char_hex_string(self):
        fp = _embedding_fingerprint([1.0, 2.0, 3.0])
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic_for_same_input(self):
        emb = [0.1, 0.2, 0.3]
        assert _embedding_fingerprint(emb) == _embedding_fingerprint(emb)

    def test_different_embeddings_produce_different_fingerprints(self):
        assert _embedding_fingerprint([1.0]) != _embedding_fingerprint([2.0])


# ── _cosine_similarity() ──────────────────────────────────────────────────────


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        v = [0.3, 0.4, 0.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_score_minus_one(self):
        assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == pytest.approx(0.0)

    def test_pure_python_fallback(self):
        """Cosine similarity works when numpy is unavailable."""
        with patch.dict("sys.modules", {"numpy": None}):
            result = _cosine_similarity([3.0, 4.0], [3.0, 4.0])
        assert result == pytest.approx(1.0)

    def test_non_unit_vectors_normalised(self):
        # [3, 4] and [6, 8] are parallel — cos similarity should be 1.0
        assert _cosine_similarity([3.0, 4.0], [6.0, 8.0]) == pytest.approx(1.0)


# ── get() ─────────────────────────────────────────────────────────────────────


class TestCacheGet:
    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        cache = RedisSemanticCache(_make_config(enabled=False), _redis=_make_redis())
        assert await cache.get([1.0, 2.0, 3.0]) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_index_is_empty(self):
        redis = _make_redis()
        redis.hgetall = AsyncMock(return_value={})
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        assert await cache.get([1.0, 2.0, 3.0]) is None

    @pytest.mark.asyncio
    async def test_returns_none_when_similarity_below_threshold(self):
        # orthogonal vectors → cosine similarity = 0.0, well below 0.97
        query_emb = [1.0, 0.0, 0.0]
        stored_emb = [0.0, 1.0, 0.0]
        fp = _embedding_fingerprint(stored_emb)

        redis = _make_redis()
        redis.hgetall = AsyncMock(return_value={fp: "1"})
        redis.get = AsyncMock(return_value=json.dumps(stored_emb).encode())

        cache = RedisSemanticCache(_make_config(threshold=0.97), _redis=redis)
        assert await cache.get(query_emb) is None

    @pytest.mark.asyncio
    async def test_returns_cached_entry_when_similarity_above_threshold(self):
        emb = [1.0, 0.0, 0.0]  # identical query → similarity 1.0
        fp = _embedding_fingerprint(emb)
        entry_dict = {
            "query_hash": fp,
            "response": "cached response",
            "embedding": emb,
            "ttl_seconds": 3600,
            "created_at": "2024-01-01T00:00:00",
        }

        redis = _make_redis()
        redis.hgetall = AsyncMock(return_value={fp: "1"})

        async def get_side_effect(key):
            if ":emb:" in key:
                return json.dumps(emb).encode()
            if ":resp:" in key:
                return json.dumps(entry_dict).encode()
            return None

        redis.get = get_side_effect

        cache = RedisSemanticCache(_make_config(threshold=0.5), _redis=redis)
        result = await cache.get(emb)
        assert result is not None
        assert result.response == "cached response"

    @pytest.mark.asyncio
    async def test_skips_expired_embedding_entry(self):
        fp = "somefingerprint1"
        redis = _make_redis()
        # index has the key but the emb key has expired (returns None)
        redis.hgetall = AsyncMock(return_value={fp: "1"})
        redis.get = AsyncMock(return_value=None)

        cache = RedisSemanticCache(_make_config(), _redis=redis)
        assert await cache.get([1.0, 0.0, 0.0]) is None

    @pytest.mark.asyncio
    async def test_handles_bytes_fingerprint_in_index(self):
        emb = [1.0, 0.0, 0.0]
        fp = _embedding_fingerprint(emb)
        # Redis may return keys as bytes
        redis = _make_redis()
        redis.hgetall = AsyncMock(return_value={fp.encode(): "1"})

        async def get_side_effect(key):
            if ":emb:" in key:
                return json.dumps(emb).encode()
            if ":resp:" in key:
                return json.dumps({
                    "query_hash": fp,
                    "response": "ok",
                    "embedding": emb,
                    "ttl_seconds": 60,
                    "created_at": "2024-01-01T00:00:00",
                }).encode()
            return None

        redis.get = get_side_effect

        cache = RedisSemanticCache(_make_config(threshold=0.5), _redis=redis)
        result = await cache.get(emb)
        assert result is not None


# ── set() ─────────────────────────────────────────────────────────────────────


class TestCacheSet:
    @pytest.mark.asyncio
    async def test_disabled_is_noop(self):
        redis = _make_redis()
        cache = RedisSemanticCache(_make_config(enabled=False), _redis=redis)
        await cache.set([1.0], "response")
        redis.pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_executes_pipeline(self):
        pipe = _make_pipeline()
        redis = _make_redis()
        redis.pipeline = MagicMock(return_value=pipe)
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.set([1.0, 2.0], "my response")
        pipe.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_embedding_and_response_keys(self):
        pipe = _make_pipeline()
        redis = _make_redis()
        redis.pipeline = MagicMock(return_value=pipe)
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.set([1.0, 2.0], "my response")
        # Two pipe.set calls: one for emb key, one for resp key
        assert pipe.set.call_count == 2

    @pytest.mark.asyncio
    async def test_custom_ttl_passed_to_pipeline(self):
        pipe = _make_pipeline()
        redis = _make_redis()
        redis.pipeline = MagicMock(return_value=pipe)
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.set([1.0], "response", ttl_seconds=120)
        for call in pipe.set.call_args_list:
            assert call.kwargs.get("ex") == 120

    @pytest.mark.asyncio
    async def test_default_ttl_used_when_not_specified(self):
        pipe = _make_pipeline()
        redis = _make_redis()
        redis.pipeline = MagicMock(return_value=pipe)
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.set([1.0], "response")
        for call in pipe.set.call_args_list:
            assert call.kwargs.get("ex") == 3600  # from config

    @pytest.mark.asyncio
    async def test_index_updated_with_fingerprint(self):
        pipe = _make_pipeline()
        redis = _make_redis()
        redis.pipeline = MagicMock(return_value=pipe)
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.set([1.0], "response")
        pipe.hset.assert_called_once()


# ── invalidate() ──────────────────────────────────────────────────────────────


class TestCacheInvalidate:
    @pytest.mark.asyncio
    async def test_returns_count_of_scanned_keys(self):
        keys = [b"test:cache:emb:abc", b"test:cache:resp:abc"]
        redis = _make_redis(scan_keys=keys)
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        count = await cache.invalidate()
        assert count == 2

    @pytest.mark.asyncio
    async def test_deletes_each_scanned_key(self):
        keys = [b"test:cache:emb:abc", b"test:cache:resp:abc"]
        redis = _make_redis(scan_keys=keys)
        delete_calls: list = []
        redis.delete = AsyncMock(side_effect=lambda k: delete_calls.append(k))
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.invalidate()
        assert b"test:cache:emb:abc" in delete_calls
        assert b"test:cache:resp:abc" in delete_calls

    @pytest.mark.asyncio
    async def test_always_deletes_index_key(self):
        redis = _make_redis(scan_keys=[])
        delete_calls: list = []
        redis.delete = AsyncMock(side_effect=lambda k: delete_calls.append(k))
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        await cache.invalidate()
        assert "test:cache:index" in delete_calls

    @pytest.mark.asyncio
    async def test_returns_zero_when_nothing_to_delete(self):
        redis = _make_redis(scan_keys=[])
        cache = RedisSemanticCache(_make_config(), _redis=redis)
        count = await cache.invalidate()
        assert count == 0
