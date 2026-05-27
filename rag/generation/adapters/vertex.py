"""
Vertex AI adapter — Gemini models via google-cloud-aiplatform.

The SDK is imported lazily so the package does not require it at import time.
Authentication uses Application Default Credentials (ADC); no explicit key
configuration is needed when running on GCP with a workload-identity SA.
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from rag.core.schemas import GenerationConfig
from rag.generation.protocols import GeneratedAnswer
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)


class VertexAIAdapter:
    """Gemini generation via the Vertex AI GenerativeModel API."""

    def __init__(self, config: GenerationConfig) -> None:
        self._config = config
        self._client = None  # initialised lazily

    @property
    def provider_name(self) -> str:
        return "vertex_ai"

    @property
    def model_name(self) -> str:
        return self._config.model

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import vertexai  # type: ignore[import]
            from vertexai.generative_models import GenerativeModel  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-aiplatform is required for VertexAIAdapter — "
                "install it with: pip install google-cloud-aiplatform"
            ) from exc

        vertexai.init(
            project=self._config.project_id,
            location=self._config.location,
        )
        self._client = GenerativeModel(
            self._config.model,
            system_instruction=None,  # set per-request
        )
        return self._client

    async def generate(
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> GeneratedAnswer:
        try:
            from vertexai.generative_models import (  # type: ignore[import]
                GenerationConfig as VxGenerationConfig,
                GenerativeModel,
            )
        except ImportError as exc:
            raise RuntimeError("google-cloud-aiplatform not installed") from exc

        with record_span(
            "generation.vertex_ai",
            **{RAGAttributes.TOKENS_IN: 0},
        ) as span:
            t0 = time.monotonic()
            model = GenerativeModel(
                self._config.model,
                system_instruction=system,
            )
            gen_cfg = VxGenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=self._config.top_p,
            )
            response = await model.generate_content_async(
                user_message,
                generation_config=gen_cfg,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            answer = response.text
            usage = response.usage_metadata
            tokens_in = getattr(usage, "prompt_token_count", 0)
            tokens_out = getattr(usage, "candidates_token_count", 0)

            span.set_attribute(RAGAttributes.TOKENS_IN, tokens_in)
            span.set_attribute(RAGAttributes.TOKENS_OUT, tokens_out)
            log.info(
                "generation.vertex_ai.complete",
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
                provider="vertex_ai",
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
        try:
            from vertexai.generative_models import (  # type: ignore[import]
                GenerationConfig as VxGenerationConfig,
                GenerativeModel,
            )
        except ImportError as exc:
            raise RuntimeError("google-cloud-aiplatform not installed") from exc

        model = GenerativeModel(
            self._config.model,
            system_instruction=system,
        )
        gen_cfg = VxGenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            top_p=self._config.top_p,
        )
        async for chunk in await model.generate_content_async(
            user_message,
            generation_config=gen_cfg,
            stream=True,
        ):
            if chunk.text:
                yield chunk.text
