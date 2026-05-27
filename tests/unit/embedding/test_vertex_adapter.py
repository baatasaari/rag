"""
Tests for rag.embedding.adapters.vertex — VertexEmbeddingAdapter.

Provides a vertexai stub at sys.modules level so the suite runs without
the real SDK installed.  If the real SDK is present, the stub is not
applied (setdefault).
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub out the vertexai package before importing the adapter.
# Using setdefault means we never overwrite a real installation.
# ---------------------------------------------------------------------------

_STUB_LM = MagicMock()


class _StubTextEmbeddingInput:
    """Minimal stand-in for vertexai.language_models.TextEmbeddingInput."""

    def __init__(self, text: str, task_type: str | None = None) -> None:
        self.text = text
        self.task_type = task_type


_STUB_LM.TextEmbeddingInput = _StubTextEmbeddingInput
_STUB_LM.TextEmbeddingModel = MagicMock()

sys.modules.setdefault("vertexai", MagicMock())
sys.modules.setdefault("vertexai.language_models", _STUB_LM)

# ---------------------------------------------------------------------------
# Now import the adapter (lazy SDK imports will resolve against our stubs).
# ---------------------------------------------------------------------------

from rag.core.schemas import EmbeddingConfig, EmbeddingTaskType  # noqa: E402
from rag.embedding.adapters.vertex import VertexEmbeddingAdapter  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────


class _MockEmbeddingValue:
    """Stands in for the SDK's TextEmbedding return object."""

    def __init__(self, values: list[float]) -> None:
        self.values = values


def _make_config(*, model: str = "text-embedding-004", project_id: str = "test-proj") -> EmbeddingConfig:
    return EmbeddingConfig(model=model, project_id=project_id)


def _make_adapter(
    *,
    return_values: list[list[float]] | None = None,
    model: str = "text-embedding-004",
) -> tuple[VertexEmbeddingAdapter, AsyncMock]:
    """Return (adapter, mock_client) so tests can inspect client calls."""
    mock_client = MagicMock()
    embeddings = [_MockEmbeddingValue(v) for v in (return_values or [[0.1, 0.2, 0.3]])]
    mock_client.get_embeddings_async = AsyncMock(return_value=embeddings)
    adapter = VertexEmbeddingAdapter(_make_config(model=model), _client=mock_client)
    return adapter, mock_client


# ── EmbeddingAdapter protocol properties ─────────────────────────────────────


class TestAdapterProtocol:
    def test_max_batch_size_matches_config(self):
        adapter, _ = _make_adapter()
        assert adapter.max_batch_size == adapter._config.batching.max_batch_size

    def test_model_id_matches_config_model(self):
        adapter, _ = _make_adapter(model="text-embedding-004")
        assert adapter.model_id == "text-embedding-004"

    def test_satisfies_embedding_adapter_protocol(self):
        from rag.embedding.protocols import EmbeddingAdapter

        adapter, _ = _make_adapter()
        assert isinstance(adapter, EmbeddingAdapter)


# ── embed() output format ─────────────────────────────────────────────────────


class TestEmbedOutput:
    @pytest.mark.asyncio
    async def test_returns_list_of_float_lists(self):
        adapter, _ = _make_adapter(return_values=[[0.1, 0.2, 0.3]])
        result = await adapter.embed(["hello"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=3)
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    @pytest.mark.asyncio
    async def test_one_embedding_per_text(self):
        values = [[float(i)] for i in range(4)]
        adapter, mock_client = _make_adapter()
        mock_client.get_embeddings_async = AsyncMock(
            return_value=[_MockEmbeddingValue(v) for v in values]
        )
        result = await adapter.embed(
            ["a", "b", "c", "d"], EmbeddingTaskType.RETRIEVAL_QUERY, dimensions=1
        )
        assert len(result) == 4

    @pytest.mark.asyncio
    async def test_embedding_values_preserved(self):
        expected = [0.11, 0.22, 0.33]
        adapter, _ = _make_adapter(return_values=[expected])
        result = await adapter.embed(["text"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=3)
        assert result[0] == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_returns_plain_list_not_sdk_object(self):
        adapter, _ = _make_adapter(return_values=[[0.1, 0.2]])
        result = await adapter.embed(["text"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=2)
        assert type(result[0]) is list


# ── embed() API call structure ────────────────────────────────────────────────


class TestEmbedAPICall:
    @pytest.mark.asyncio
    async def test_calls_get_embeddings_async(self):
        adapter, mock_client = _make_adapter()
        await adapter.embed(["hello"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=768)
        mock_client.get_embeddings_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_output_dimensionality(self):
        adapter, mock_client = _make_adapter()
        await adapter.embed(["hello"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=256)
        _, call_kwargs = mock_client.get_embeddings_async.call_args
        assert call_kwargs.get("output_dimensionality") == 256

    @pytest.mark.asyncio
    async def test_task_type_embedded_in_inputs(self):
        inputs_seen: list = []

        async def capturing_call(inputs, **kwargs):
            inputs_seen.extend(inputs)
            return [_MockEmbeddingValue([0.1])]

        adapter, mock_client = _make_adapter()
        mock_client.get_embeddings_async = capturing_call

        await adapter.embed(["text"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=1)
        assert inputs_seen[0].task_type == EmbeddingTaskType.RETRIEVAL_DOCUMENT.value

    @pytest.mark.asyncio
    async def test_text_content_passed_in_inputs(self):
        inputs_seen: list = []

        async def capturing_call(inputs, **kwargs):
            inputs_seen.extend(inputs)
            return [_MockEmbeddingValue([0.1]) for _ in inputs]

        adapter, mock_client = _make_adapter()
        mock_client.get_embeddings_async = capturing_call

        await adapter.embed(["hello world"], EmbeddingTaskType.RETRIEVAL_QUERY, dimensions=1)
        assert inputs_seen[0].text == "hello world"

    @pytest.mark.asyncio
    async def test_multiple_texts_produce_multiple_inputs(self):
        inputs_seen: list = []

        async def capturing_call(inputs, **kwargs):
            inputs_seen.extend(inputs)
            return [_MockEmbeddingValue([float(i)]) for i in range(len(inputs))]

        adapter, mock_client = _make_adapter()
        mock_client.get_embeddings_async = capturing_call

        texts = ["one", "two", "three"]
        await adapter.embed(texts, EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=1)
        assert len(inputs_seen) == 3
        assert [inp.text for inp in inputs_seen] == texts

    @pytest.mark.asyncio
    async def test_different_task_types_produce_different_input_task_types(self):
        seen_task_types: list[str] = []

        async def capturing_call(inputs, **kwargs):
            seen_task_types.extend(inp.task_type for inp in inputs)
            return [_MockEmbeddingValue([0.1]) for _ in inputs]

        adapter, mock_client = _make_adapter()
        mock_client.get_embeddings_async = capturing_call

        await adapter.embed(["a"], EmbeddingTaskType.RETRIEVAL_DOCUMENT, dimensions=1)
        await adapter.embed(["b"], EmbeddingTaskType.RETRIEVAL_QUERY, dimensions=1)

        assert seen_task_types[0] == EmbeddingTaskType.RETRIEVAL_DOCUMENT.value
        assert seen_task_types[1] == EmbeddingTaskType.RETRIEVAL_QUERY.value


# ── _get_client() lazy init ───────────────────────────────────────────────────


class TestGetClient:
    def test_returns_injected_client_without_init(self):
        mock_client = MagicMock()
        adapter = VertexEmbeddingAdapter(_make_config(), _client=mock_client)
        assert adapter._get_client() is mock_client

    def test_raises_runtime_error_without_project_id(self):
        adapter = VertexEmbeddingAdapter(EmbeddingConfig(model="text-embedding-004"))
        with pytest.raises(RuntimeError, match="project_id"):
            adapter._get_client()
