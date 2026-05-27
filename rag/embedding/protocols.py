"""
EmbeddingAdapter protocol — the contract every embedding backend must satisfy.

Decouples the EmbeddingEngine from any specific provider so swapping
Vertex AI for Cohere / HuggingFace / Bedrock requires only a new adapter
file, zero changes to the engine.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from rag.core.schemas import EmbeddingTaskType


@runtime_checkable
class EmbeddingAdapter(Protocol):
    """Minimal interface an embedding backend must implement.

    Responsibilities:
      - Issue the raw API call for a single batch of texts.
      - Respect the task_type and dimensions requested by the engine.
      - Raise on permanent errors; let the engine/circuit-breaker decide retry.

    The engine owns batching, concurrency, circuit-breaking, fallback, and
    cost tracking.  The adapter owns only the provider-specific wire protocol.
    """

    @property
    def max_batch_size(self) -> int:
        """Maximum texts per single embed() call (provider hard limit)."""
        ...

    @property
    def model_id(self) -> str:
        """Identifies the model in logs and span attributes."""
        ...

    async def embed(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType,
        *,
        dimensions: int,
    ) -> list[list[float]]:
        """Embed *texts* and return one float vector per text.

        Args:
            texts:      Non-empty list of strings (engine guarantees this).
            task_type:  Asymmetric task hint for the model.
            dimensions: Requested output dimensionality.

        Returns:
            Parallel list of float vectors — ``results[i]`` is the embedding
            for ``texts[i]``.
        """
        ...
