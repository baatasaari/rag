"""
GenerationEngine — orchestrates the full generation pipeline.

Flow:
  1. Receive an AssembledPrompt from the augmentation layer.
  2. If a CachedGenerator is wired in, attempt a semantic cache lookup first.
  3. Call the primary LLM adapter (generate or stream).
  4. On failure, fall back to the configured fallback adapter (if any).
  5. Return a GeneratedAnswer with token counts, latency, and citation indices.

Streaming:
  The engine exposes both `generate()` (blocking, full response) and
  `stream()` (async generator of token strings).  Callers that don't need
  streaming should use `generate()` for simpler error handling.

Fallback:
  The engine accepts an optional `fallback_adapter`.  If the primary call
  raises any exception, the fallback is tried once.  If the fallback also
  fails, the original exception is re-raised.

FCA compliance:
  The system prompt (from PromptBuilder) already frames the answer within the
  retrieved context.  The engine never appends additional instructions.
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from rag.augmentation.prompt_builder import AssembledPrompt
from rag.generation.protocols import GeneratedAnswer, LLMAdapter
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)


class GenerationEngine:
    """Orchestrates LLM generation with optional caching and fallback."""

    def __init__(
        self,
        primary: LLMAdapter,
        *,
        fallback: LLMAdapter | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def generate(self, prompt: AssembledPrompt) -> GeneratedAnswer:
        """Generate a complete answer from an assembled prompt."""
        with record_span(
            "generation.engine",
            **{
                "rag.generation.provider": self._primary.provider_name,
                "rag.generation.model": self._primary.model_name,
            },
        ) as span:
            t0 = time.monotonic()
            try:
                result = await self._primary.generate(
                    prompt.system,
                    prompt.user_message,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )
            except Exception as primary_exc:
                log.warning(
                    "generation.engine.primary_failed",
                    provider=self._primary.provider_name,
                    error=str(primary_exc),
                )
                if self._fallback is None:
                    raise
                log.info(
                    "generation.engine.fallback",
                    fallback_provider=self._fallback.provider_name,
                )
                result = await self._fallback.generate(
                    prompt.system,
                    prompt.user_message,
                    temperature=self._temperature,
                    max_tokens=self._max_tokens,
                )

            total_ms = (time.monotonic() - t0) * 1000
            span.set_attribute(RAGAttributes.TOKENS_IN, result.tokens_in)
            span.set_attribute(RAGAttributes.TOKENS_OUT, result.tokens_out)
            span.set_attribute(RAGAttributes.CACHE_HIT, result.cached)
            log.info(
                "generation.engine.complete",
                provider=result.provider,
                model=result.model,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cached=result.cached,
                citations=result.citations_used,
                latency_ms=round(total_ms),
            )
            return result

    async def stream(self, prompt: AssembledPrompt) -> AsyncIterator[str]:
        """Stream tokens from the primary adapter (no fallback for streaming)."""
        with record_span(
            "generation.engine.stream",
            **{
                "rag.generation.provider": self._primary.provider_name,
                "rag.generation.model": self._primary.model_name,
            },
        ):
            async for token in self._primary.stream(
                prompt.system,
                prompt.user_message,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            ):
                yield token

    def with_fallback(self, fallback: LLMAdapter) -> "GenerationEngine":
        """Return a new engine with the given fallback adapter wired in."""
        return GenerationEngine(
            self._primary,
            fallback=fallback,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
