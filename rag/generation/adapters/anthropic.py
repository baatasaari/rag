"""
Anthropic adapter — Claude models via the anthropic SDK.

The SDK is imported lazily.  Requires config.api_key (SecretStr).
Streaming uses the Messages API streaming events.
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from rag.core.schemas import GenerationConfig
from rag.generation.protocols import GeneratedAnswer
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)


def _get_client(api_key: str):
    try:
        import anthropic  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package is required for AnthropicAdapter — "
            "install it with: pip install anthropic"
        ) from exc
    return anthropic.AsyncAnthropic(api_key=api_key)


class AnthropicAdapter:
    """Claude generation via the Anthropic Messages API."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        if config.api_key is None:
            raise ValueError("GenerationConfig.api_key is required for AnthropicAdapter.")
        self._api_key = config.api_key.get_secret_value()

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._config.model

    async def generate(
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> GeneratedAnswer:
        client = _get_client(self._api_key)

        with record_span("generation.anthropic") as span:
            t0 = time.monotonic()
            response = await client.messages.create(
                model=self._config.model,
                system=system,
                messages=[{"role": "user", "content": user_message}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            answer = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens

            span.set_attribute(RAGAttributes.TOKENS_IN, tokens_in)
            span.set_attribute(RAGAttributes.TOKENS_OUT, tokens_out)
            log.info(
                "generation.anthropic.complete",
                model=self._config.model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=round(latency_ms),
            )
            return GeneratedAnswer(
                answer=answer,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model=self._config.model,
                provider="anthropic",
                latency_ms=latency_ms,
            )

    async def stream(
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        client = _get_client(self._api_key)
        async with client.messages.stream(
            model=self._config.model,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text
