"""
Vertex AI text-embedding-004 adapter for the LBG RAG Platform.

Registered as: @register("embedding", "vertex_ai")

Wraps the google-cloud-aiplatform SDK's TextEmbeddingModel, translating the
EmbeddingAdapter protocol into the Vertex AI async call pattern.

Key behaviours:
  - Uses get_embeddings_async() for non-blocking IO.
  - TextEmbeddingInput carries the task_type per text (SDK requirement).
  - output_dimensionality requests Matryoshka truncation from the API itself
    rather than slicing the full vector in Python.
  - Lazy client init: injecting _client bypasses all auth (testing / DI).
"""

from __future__ import annotations

from typing import Any

from rag.core.registry import register
from rag.core.schemas import EmbeddingConfig, EmbeddingTaskType
from rag.observability.logging import get_logger

log = get_logger(__name__)


@register("embedding", "vertex_ai")
class VertexEmbeddingAdapter:
    """Vertex AI TextEmbeddingModel adapter.

    Args:
        config:  EmbeddingConfig from RAGConfig.embedding.
        _client: Injected TextEmbeddingModel (for testing — skips SDK init).
    """

    def __init__(
        self,
        config: EmbeddingConfig,
        *,
        _client: Any = None,
    ) -> None:
        self._config = config
        self._client = _client

    # ------------------------------------------------------------------
    # EmbeddingAdapter protocol
    # ------------------------------------------------------------------

    @property
    def max_batch_size(self) -> int:
        return self._config.batching.max_batch_size

    @property
    def model_id(self) -> str:
        return self._config.model

    async def embed(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType,
        *,
        dimensions: int,
    ) -> list[list[float]]:
        """Call Vertex AI and return one embedding vector per text.

        Imports TextEmbeddingInput lazily so the module can be loaded even
        when google-cloud-aiplatform is absent (e.g. minimal test envs).
        """
        from vertexai.language_models import TextEmbeddingInput  # noqa: PLC0415

        client = self._get_client()
        inputs = [
            TextEmbeddingInput(text=t, task_type=task_type.value) for t in texts
        ]
        embeddings = await client.get_embeddings_async(
            inputs,
            output_dimensionality=dimensions,
        )
        return [list(e.values) for e in embeddings]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            import vertexai  # noqa: PLC0415
            from vertexai.language_models import TextEmbeddingModel  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-aiplatform is required for Vertex AI embeddings. "
                "Install with: pip install google-cloud-aiplatform"
            ) from exc

        if not self._config.project_id:
            raise RuntimeError(
                "embedding.project_id is not set. "
                "Populate it from ${GCP_PROJECT_ID} in config."
            )

        vertexai.init(
            project=self._config.project_id,
            location=self._config.location,
        )
        self._client = TextEmbeddingModel.from_pretrained(self._config.model)
        log.info(
            "embedding.vertex_client_initialised",
            model=self._config.model,
            project=self._config.project_id,
            location=self._config.location,
        )
        return self._client
