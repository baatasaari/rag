"""
Semantic cache integration for the generation layer.

CachedGenerator wraps any LLMAdapter and a SemanticCache.  On each call it:
  1. Embeds the query with embed_fn.
  2. Checks the semantic cache — if a sufficiently similar prior query exists,
     returns the cached answer immediately (cache hit).
  3. On a miss: delegates to the wrapped adapter, stores the answer, returns it.

Streaming cache hits re-emit the cached text word-by-word so the caller's
streaming interface remains consistent even when the answer is served from cache.

Cache storage uses the full assembled prompt text as the semantic key (not just
the raw user query) to avoid false hits across different context windows.
"""

from __future__ import annotations

import time
from typing import AsyncIterator, Callable, Awaitable

from rag.generation.protocols import GeneratedAnswer, LLMAdapter
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.storage.protocols import CacheEntry, SemanticCache

log = get_logger(__name__)

EmbedFn = Callable[[str], Awaitable[list[float]]]


class CachedGenerator:
    """Cache-first LLM generation backed by a SemanticCache."""

    def __init__(
        self,
        adapter: LLMAdapter,
        cache: SemanticCache,
        embed_fn: EmbedFn,
        ttl_seconds: int = 3600,
    ) -> None:
        self._adapter = adapter
        self._cache = cache
        self._embed_fn = embed_fn
        self._ttl = ttl_seconds

    async def generate(
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        cache_key_text: str | None = None,
    ) -> GeneratedAnswer:
        """Generate or serve from cache.

        Args:
            cache_key_text: Text to embed for cache lookup/store.
                            Defaults to user_message if not provided.
        """
        key_text = cache_key_text or user_message

        with record_span("generation.cache") as span:
            t0 = time.monotonic()
            embedding = await self._embed_fn(key_text)

            # Cache probe
            entry: CacheEntry | None = await self._cache.get(embedding)
            if entry is not None:
                latency_ms = (time.monotonic() - t0) * 1000
                span.set_attribute(RAGAttributes.CACHE_HIT, True)
                log.info("generation.cache.hit", latency_ms=round(latency_ms))
                return GeneratedAnswer(
                    answer=entry.response,
                    tokens_in=0,
                    tokens_out=0,
                    model=self._adapter.model_name,
                    provider=self._adapter.provider_name,
                    cached=True,
                    latency_ms=latency_ms,
                )

            span.set_attribute(RAGAttributes.CACHE_HIT, False)

            # Cache miss → generate
            result = await self._adapter.generate(
                system,
                user_message,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Store in cache
            try:
                await self._cache.set(embedding, result.answer, ttl_seconds=self._ttl)
            except Exception as exc:
                log.warning("generation.cache.store_failed", error=str(exc))

            log.info(
                "generation.cache.miss",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
            )
            return result

    async def stream(
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        cache_key_text: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens, serving from cache when possible.

        Cache hits are re-emitted word-by-word for a consistent streaming UX.
        Cache misses accumulate the stream and write back on completion.
        """
        key_text = cache_key_text or user_message
        embedding = await self._embed_fn(key_text)

        entry: CacheEntry | None = await self._cache.get(embedding)
        if entry is not None:
            log.info("generation.cache.stream_hit")
            # Re-emit cached words to preserve streaming interface
            for word in entry.response.split(" "):
                yield word + " "
            return

        # Cache miss — stream from adapter and accumulate
        accumulated: list[str] = []
        async for token in self._adapter.stream(
            system,
            user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            accumulated.append(token)
            yield token

        full_response = "".join(accumulated)
        if full_response:
            try:
                await self._cache.set(embedding, full_response, ttl_seconds=self._ttl)
            except Exception as exc:
                log.warning("generation.cache.store_failed", error=str(exc))
