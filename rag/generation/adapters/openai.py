"""
OpenAI / Azure OpenAI adapter — via the openai SDK.

For AZURE_OPENAI:  requires config.api_key and sets base_url from project_id
(treated as the Azure resource endpoint, e.g. https://<resource>.openai.azure.com).

For OPENAI:  requires config.api_key and uses the default OpenAI base_url.

The SDK is imported lazily.
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from rag.core.schemas import GenerationConfig, LLMProvider
from rag.generation.protocols import GeneratedAnswer
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)


def _get_client(config: GenerationConfig):
    try:
        from openai import AsyncAzureOpenAI, AsyncOpenAI  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "openai package is required for OpenAIAdapter — "
            "install it with: pip install openai"
        ) from exc

    api_key = config.api_key.get_secret_value() if config.api_key else None

    if config.provider == LLMProvider.AZURE_OPENAI:
        return AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=config.project_id or "",  # project_id holds the Azure endpoint
            api_version="2024-02-01",
        )
    return AsyncOpenAI(api_key=api_key)


class OpenAIAdapter:
    """Chat completions via OpenAI or Azure OpenAI."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        if config.api_key is None and config.provider == LLMProvider.OPENAI:
            raise ValueError("GenerationConfig.api_key is required for OpenAIAdapter.")

    @property
    def provider_name(self) -> str:
        return self._config.provider.value

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
        client = _get_client(self._config)

        with record_span("generation.openai") as span:
            t0 = time.monotonic()
            response = await client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            answer = response.choices[0].message.content or ""
            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0

            span.set_attribute(RAGAttributes.TOKENS_IN, tokens_in)
            span.set_attribute(RAGAttributes.TOKENS_OUT, tokens_out)
            log.info(
                "generation.openai.complete",
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
                provider=self._config.provider.value,
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
        client = _get_client(self._config)
        stream = await client.chat.completions.create(
            model=self._config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
