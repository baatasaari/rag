"""
EmbeddingEngine — orchestration layer for all embedding operations.

Responsibilities (the adapter handles none of these):
  - Enforce asymmetric task types: RETRIEVAL_DOCUMENT at ingestion,
    RETRIEVAL_QUERY at query time.  Non-negotiable for correct retrieval.
  - Batch texts into chunks ≤ adapter.max_batch_size.
  - Dispatch batches concurrently up to max_concurrent_batches.
  - Circuit-break the primary adapter; fall back to the fallback adapter when
    the primary is open or raises.
  - Track embedding API cost as an OTel counter metric.
  - Emit OTel spans for each top-level embed call.

The engine is provider-agnostic — it depends only on EmbeddingAdapter.
"""

from __future__ import annotations

import asyncio
from typing import Any

from rag.core.schemas import (
    CircuitBreakerConfig,
    EmbeddingConfig,
    EmbeddingTaskType,
)
from rag.embedding.protocols import EmbeddingAdapter
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.storage.circuit_breaker import CircuitBreaker

log = get_logger(__name__)


class EmbeddingEngine:
    """Provider-agnostic embedding orchestrator.

    Args:
        config:                  EmbeddingConfig from RAGConfig.embedding.
        adapter:                 Primary embedding backend.
        fallback_adapter:        Optional fallback used when the primary fails.
        circuit_breaker_config:  If set and enabled, wraps each adapter call.
    """

    def __init__(
        self,
        config: EmbeddingConfig,
        adapter: EmbeddingAdapter,
        *,
        fallback_adapter: EmbeddingAdapter | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._fallback = fallback_adapter
        self._breaker: CircuitBreaker | None = (
            CircuitBreaker("vertex_ai_embedding", circuit_breaker_config)
            if circuit_breaker_config and circuit_breaker_config.enabled
            else None
        )
        self._cost_counter = self._init_cost_counter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_for_ingestion(self, texts: list[str]) -> list[list[float]]:
        """Embed documents for indexing.  Always uses RETRIEVAL_DOCUMENT."""
        with record_span(
            "embedding.ingestion",
            **{
                RAGAttributes.MODEL: self._config.model,
                RAGAttributes.EMBEDDING_TASK_TYPE: self._config.task_types.ingestion.value,
                "rag.embedding.input_count": len(texts),
            },
        ):
            return await self._embed(
                texts,
                self._config.task_types.ingestion,
                dimensions=self._config.dimensions.default,
            )

    async def embed_for_query(self, texts: list[str]) -> list[list[float]]:
        """Embed a user query.  Always uses RETRIEVAL_QUERY."""
        with record_span(
            "embedding.query",
            **{
                RAGAttributes.MODEL: self._config.model,
                RAGAttributes.EMBEDDING_TASK_TYPE: self._config.task_types.query.value,
                "rag.embedding.input_count": len(texts),
            },
        ):
            return await self._embed(
                texts,
                self._config.task_types.query,
                dimensions=self._config.dimensions.default,
            )

    async def embed_for_cache(self, texts: list[str]) -> list[list[float]]:
        """Embed for semantic cache lookup.  Uses fast_path dimensions."""
        with record_span("embedding.cache_lookup"):
            return await self._embed(
                texts,
                self._config.task_types.cache_lookup,
                dimensions=self._config.dimensions.fast_path,
            )

    async def embed(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType,
    ) -> list[list[float]]:
        """Generic embed call for callers that manage task_type themselves."""
        return await self._embed(
            texts,
            task_type,
            dimensions=self._config.dimensions.default,
        )

    # ------------------------------------------------------------------
    # Internal orchestration
    # ------------------------------------------------------------------

    async def _embed(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType,
        *,
        dimensions: int,
    ) -> list[list[float]]:
        if not texts:
            return []

        self._track_cost(texts)
        batches = self._split_batches(texts)
        sem = asyncio.Semaphore(self._config.batching.max_concurrent_batches)

        async def _one(batch: list[str]) -> list[list[float]]:
            async with sem:
                return await self._embed_batch(batch, task_type, dimensions)

        results = await asyncio.gather(*[_one(b) for b in batches])
        return [emb for batch_result in results for emb in batch_result]

    async def _embed_batch(
        self,
        batch: list[str],
        task_type: EmbeddingTaskType,
        dimensions: int,
    ) -> list[list[float]]:
        """Embed one batch, with circuit-breaker and fallback handling."""
        try:
            coro = self._adapter.embed(batch, task_type, dimensions=dimensions)
            if self._breaker:
                return await self._breaker.call(coro)
            return await coro
        except Exception as exc:
            if (
                self._fallback is not None
                and self._config.fallback is not None
                and self._config.fallback.enabled
            ):
                log.warning(
                    "embedding.fallback_activated",
                    primary_model=self._config.model,
                    fallback_model=self._config.fallback.model,
                    error=str(exc),
                )
                return await self._fallback.embed(
                    batch,
                    EmbeddingTaskType.SEMANTIC_SIMILARITY,
                    dimensions=dimensions,
                )
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _split_batches(self, texts: list[str]) -> list[list[str]]:
        size = self._config.batching.max_batch_size
        return [texts[i : i + size] for i in range(0, len(texts), size)]

    def _track_cost(self, texts: list[str]) -> None:
        if self._cost_counter is None:
            return
        total_chars = sum(len(t) for t in texts)
        cost = total_chars * self._config.cost_tracking.price_per_1k_chars / 1000
        try:
            self._cost_counter.add(cost)
        except Exception:
            pass

    def _init_cost_counter(self) -> Any:
        if not self._config.cost_tracking.enabled:
            return None
        try:
            import opentelemetry.metrics as _otel_metrics  # noqa: PLC0415

            meter = _otel_metrics.get_meter(__name__)
            return meter.create_counter(
                self._config.cost_tracking.metric_name,
                unit="USD",
                description="Embedding API cost in USD",
            )
        except Exception:
            return None
