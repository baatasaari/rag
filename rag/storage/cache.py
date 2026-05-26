"""
Redis-backed semantic cache for the LBG RAG Platform.

Stores query embeddings alongside their generated responses.  On cache lookup,
finds the nearest stored embedding by cosine similarity; if that similarity
exceeds the configured threshold (default 0.97), returns the cached response
without running the full RAG pipeline.

Key layout in Redis:
  {prefix}:cache:emb:{hash16}   → JSON-encoded embedding (list[float])
  {prefix}:cache:resp:{hash16}  → JSON-encoded CacheEntry (response + metadata)
  {prefix}:cache:index          → Redis Hash mapping hash16 → 1 (for SCAN)

Where hash16 = first 16 chars of SHA-256 of the string representation of the
embedding vector (used as a compact fingerprint, not for cryptographic purposes).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from rag.core.schemas import CacheConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.storage.protocols import CacheEntry

log = get_logger(__name__)


def _embedding_fingerprint(embedding: list[float]) -> str:
    return hashlib.sha256(str(embedding).encode()).hexdigest()[:16]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors.  Uses numpy if available."""
    try:
        import numpy as np

        a_arr, b_arr = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
        norm_a, norm_b = np.linalg.norm(a_arr), np.linalg.norm(b_arr)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0


class RedisSemanticCache:
    """Redis-backed semantic cache.

    Args:
        config: CacheConfig from RAGConfig.storage.cache.
        _redis: Injected Redis client (for testing).
    """

    def __init__(self, config: CacheConfig, *, _redis: Any = None) -> None:
        self._config = config
        self._cache_cfg = config.semantic_cache
        self._prefix = config.key_prefix
        self._ttl = config.ttl_seconds
        self._redis = _redis  # None → lazy-init

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, query_embedding: list[float]) -> CacheEntry | None:
        """Return a cached entry if a similar-enough query was seen before."""
        if not self._cache_cfg.enabled:
            return None

        with record_span("storage.cache.get") as span:
            result = await self._find_similar(query_embedding)
            hit = result is not None
            span.set_attribute(RAGAttributes.CACHE_HIT, hit)
            self._record_metrics(hit)
            return result

    async def set(
        self,
        query_embedding: list[float],
        response: str,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Cache *response* keyed by the nearest embedding fingerprint."""
        if not self._cache_cfg.enabled:
            return

        with record_span("storage.cache.set"):
            fingerprint = _embedding_fingerprint(query_embedding)
            ttl = ttl_seconds or self._ttl
            redis = await self._get_redis()

            emb_key = f"{self._prefix}:cache:emb:{fingerprint}"
            resp_key = f"{self._prefix}:cache:resp:{fingerprint}"
            idx_key = f"{self._prefix}:cache:index"

            entry = CacheEntry(
                query_hash=fingerprint,
                response=response,
                embedding=query_embedding,
                ttl_seconds=ttl,
            )

            pipe = redis.pipeline()
            pipe.set(emb_key, json.dumps(query_embedding), ex=ttl)
            pipe.set(resp_key, json.dumps(_entry_to_dict(entry)), ex=ttl)
            pipe.hset(idx_key, fingerprint, 1)
            pipe.expire(idx_key, ttl)
            await pipe.execute()

    async def invalidate(self, pattern: str = "*") -> int:
        """Delete all cache keys matching *pattern*.  Returns count deleted."""
        redis = await self._get_redis()
        match_pattern = f"{self._prefix}:cache:*{pattern}*"
        deleted = 0
        async for key in redis.scan_iter(match=match_pattern):
            await redis.delete(key)
            deleted += 1
        # Also clear the index
        index_key = f"{self._prefix}:cache:index"
        await redis.delete(index_key)
        return deleted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _find_similar(self, query_embedding: list[float]) -> CacheEntry | None:
        """Scan stored embeddings and return the best match above threshold."""
        redis = await self._get_redis()
        idx_key = f"{self._prefix}:cache:index"
        index = await redis.hgetall(idx_key)
        if not index:
            return None

        best_score = -1.0
        best_fingerprint: str | None = None

        for fingerprint_bytes in index:
            fingerprint = (
                fingerprint_bytes.decode()
                if isinstance(fingerprint_bytes, bytes)
                else fingerprint_bytes
            )
            emb_key = f"{self._prefix}:cache:emb:{fingerprint}"
            raw = await redis.get(emb_key)
            if raw is None:
                continue  # expired
            stored_emb = json.loads(raw)
            score = _cosine_similarity(query_embedding, stored_emb)
            if score > best_score:
                best_score = score
                best_fingerprint = fingerprint

        if best_fingerprint is None or best_score < self._cache_cfg.threshold:
            return None

        resp_key = f"{self._prefix}:cache:resp:{best_fingerprint}"
        raw_resp = await redis.get(resp_key)
        if raw_resp is None:
            return None

        return _dict_to_entry(json.loads(raw_resp))

    async def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis

            url = None
            if self._config.url is not None:
                url = self._config.url.get_secret_value()
            self._redis = await aioredis.from_url(url or "redis://localhost:6379/0")
            return self._redis
        except ImportError as exc:
            raise RuntimeError("redis[hiredis] is required for caching.") from exc

    def _record_metrics(self, hit: bool) -> None:
        try:
            from rag.observability.metrics import get_metrics

            m = get_metrics()
            if hit:
                m.cache_hits_total.add(1)
            else:
                m.cache_misses_total.add(1)
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _entry_to_dict(entry: CacheEntry) -> dict[str, Any]:
    return {
        "query_hash": entry.query_hash,
        "response": entry.response,
        "embedding": entry.embedding,
        "ttl_seconds": entry.ttl_seconds,
        "created_at": entry.created_at.isoformat(),
    }


def _dict_to_entry(data: dict[str, Any]) -> CacheEntry:
    from datetime import datetime

    return CacheEntry(
        query_hash=data["query_hash"],
        response=data["response"],
        embedding=data["embedding"],
        ttl_seconds=data["ttl_seconds"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )
