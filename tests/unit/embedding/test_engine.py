"""
Tests for rag.embedding.engine — EmbeddingEngine orchestration.

Uses a lightweight stub adapter so no real Vertex AI calls are made.
"""

from __future__ import annotations

import pytest

from rag.core.exceptions import CircuitBreakerOpenError
from rag.core.schemas import (
    CircuitBreakerConfig,
    EmbeddingBatchingConfig,
    EmbeddingConfig,
    EmbeddingCostTrackingConfig,
    EmbeddingDimensions,
    EmbeddingFallbackConfig,
    EmbeddingTaskType,
)
from rag.embedding.engine import EmbeddingEngine
from rag.storage.circuit_breaker import reset_breakers


# ── Fixtures & helpers ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_breakers():
    reset_breakers()
    yield
    reset_breakers()


def _make_config(
    *,
    max_batch_size: int = 250,
    max_concurrent_batches: int = 10,
    default_dims: int = 768,
    fast_path_dims: int = 256,
    fallback_enabled: bool = False,
    cost_tracking: bool = False,
) -> EmbeddingConfig:
    return EmbeddingConfig(
        model="text-embedding-004",
        project_id="test-project",
        dimensions=EmbeddingDimensions(default=default_dims, fast_path=fast_path_dims),
        batching=EmbeddingBatchingConfig(
            max_batch_size=max_batch_size,
            max_concurrent_batches=max_concurrent_batches,
        ),
        fallback=EmbeddingFallbackConfig(enabled=fallback_enabled)
        if fallback_enabled
        else None,
        cost_tracking=EmbeddingCostTrackingConfig(enabled=cost_tracking),
    )


def _make_cb_config(*, failure_threshold: int = 3) -> CircuitBreakerConfig:
    return CircuitBreakerConfig(
        enabled=True,
        failure_threshold=failure_threshold,
        open_duration_seconds=60,
        success_threshold_to_close=2,
    )


class _StubAdapter:
    """In-memory adapter that records calls and optionally raises."""

    def __init__(
        self,
        *,
        dims: int = 3,
        fail: bool = False,
        fail_n_times: int = 0,
    ) -> None:
        self.calls: list[tuple[list[str], EmbeddingTaskType, int]] = []
        self._dims = dims
        self._fail = fail
        self._fail_n_times = fail_n_times
        self._call_count = 0
        self.max_batch_size = 250
        self.model_id = "stub"

    async def embed(
        self,
        texts: list[str],
        task_type: EmbeddingTaskType,
        *,
        dimensions: int,
    ) -> list[list[float]]:
        self._call_count += 1
        self.calls.append((list(texts), task_type, dimensions))
        if self._fail or self._call_count <= self._fail_n_times:
            raise RuntimeError("stub adapter failure")
        return [[float(j) for j in range(dimensions)] for _ in texts]


# ── empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    @pytest.mark.asyncio
    async def test_empty_texts_returns_empty_list(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        result = await engine.embed_for_ingestion([])
        assert result == []
        assert adapter.calls == []

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_list(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        assert await engine.embed_for_query([]) == []


# ── task-type enforcement ─────────────────────────────────────────────────────


class TestTaskTypeEnforcement:
    @pytest.mark.asyncio
    async def test_ingestion_uses_retrieval_document(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        await engine.embed_for_ingestion(["text"])
        assert adapter.calls[0][1] == EmbeddingTaskType.RETRIEVAL_DOCUMENT

    @pytest.mark.asyncio
    async def test_query_uses_retrieval_query(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        await engine.embed_for_query(["text"])
        assert adapter.calls[0][1] == EmbeddingTaskType.RETRIEVAL_QUERY

    @pytest.mark.asyncio
    async def test_cache_uses_cache_lookup_task_type(self):
        adapter = _StubAdapter()
        config = _make_config()
        engine = EmbeddingEngine(config, adapter)
        await engine.embed_for_cache(["text"])
        assert adapter.calls[0][1] == config.task_types.cache_lookup

    @pytest.mark.asyncio
    async def test_generic_embed_uses_provided_task_type(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        await engine.embed(["text"], EmbeddingTaskType.CLUSTERING)
        assert adapter.calls[0][1] == EmbeddingTaskType.CLUSTERING


# ── dimension routing ─────────────────────────────────────────────────────────


class TestDimensionRouting:
    @pytest.mark.asyncio
    async def test_ingestion_uses_default_dimensions(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(default_dims=768, fast_path_dims=256), adapter)
        await engine.embed_for_ingestion(["text"])
        assert adapter.calls[0][2] == 768

    @pytest.mark.asyncio
    async def test_query_uses_default_dimensions(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(default_dims=768, fast_path_dims=256), adapter)
        await engine.embed_for_query(["text"])
        assert adapter.calls[0][2] == 768

    @pytest.mark.asyncio
    async def test_cache_uses_fast_path_dimensions(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(default_dims=768, fast_path_dims=256), adapter)
        await engine.embed_for_cache(["text"])
        assert adapter.calls[0][2] == 256

    @pytest.mark.asyncio
    async def test_generic_embed_uses_default_dimensions(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(default_dims=768, fast_path_dims=256), adapter)
        await engine.embed(["text"], EmbeddingTaskType.RETRIEVAL_QUERY)
        assert adapter.calls[0][2] == 768


# ── output shape ──────────────────────────────────────────────────────────────


class TestOutputShape:
    @pytest.mark.asyncio
    async def test_returns_one_vector_per_text(self):
        adapter = _StubAdapter(dims=768)
        engine = EmbeddingEngine(_make_config(default_dims=768), adapter)
        result = await engine.embed_for_ingestion(["a", "b", "c"])
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_each_vector_has_correct_dimensions(self):
        adapter = _StubAdapter(dims=768)
        engine = EmbeddingEngine(_make_config(default_dims=768), adapter)
        result = await engine.embed_for_ingestion(["hello"])
        assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_single_text_returns_one_vector(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        result = await engine.embed_for_query(["what is RAG?"])
        assert len(result) == 1


# ── batching ──────────────────────────────────────────────────────────────────


class TestBatching:
    @pytest.mark.asyncio
    async def test_texts_within_batch_size_is_one_call(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(max_batch_size=10), adapter)
        await engine.embed_for_ingestion(["text"] * 10)
        assert len(adapter.calls) == 1

    @pytest.mark.asyncio
    async def test_texts_exceeding_batch_size_splits_into_multiple_calls(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(max_batch_size=10), adapter)
        # 25 texts, batch_size=10 → batches of [10, 10, 5]
        await engine.embed_for_ingestion(["text"] * 25)
        assert len(adapter.calls) == 3

    @pytest.mark.asyncio
    async def test_split_preserves_all_texts(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(max_batch_size=10), adapter)
        await engine.embed_for_ingestion(["text"] * 25)
        total_texts = sum(len(call[0]) for call in adapter.calls)
        assert total_texts == 25

    @pytest.mark.asyncio
    async def test_results_ordered_to_match_input(self):
        """Each result position must correspond to the input text at that index."""

        class _OrderedStub:
            max_batch_size = 5
            model_id = "ordered-stub"
            calls: list = []

            async def embed(self, texts, task_type, *, dimensions):
                self.calls.append(texts)
                # Encode text length in first dimension so we can verify order
                return [[float(len(t))] + [0.0] * (dimensions - 1) for t in texts]

        stub = _OrderedStub()
        texts = [f"{'x' * (i + 1)}" for i in range(12)]  # lengths 1..12
        # Use default dimensions (768/256) which satisfy schema constraints
        engine = EmbeddingEngine(_make_config(max_batch_size=5), stub)
        result = await engine.embed_for_ingestion(texts)

        assert len(result) == 12
        for i, (emb, txt) in enumerate(zip(result, texts)):
            assert emb[0] == float(len(txt)), f"Position {i} mismatched"

    @pytest.mark.asyncio
    async def test_exact_batch_boundary(self):
        """Exactly max_batch_size texts should be one call, not two."""
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(max_batch_size=8), adapter)
        await engine.embed_for_ingestion(["t"] * 8)
        assert len(adapter.calls) == 1


# ── fallback ──────────────────────────────────────────────────────────────────


class TestFallback:
    @pytest.mark.asyncio
    async def test_fallback_called_when_primary_raises(self):
        primary = _StubAdapter(fail=True)
        fallback = _StubAdapter()
        config = _make_config(fallback_enabled=True)
        engine = EmbeddingEngine(config, primary, fallback_adapter=fallback)
        result = await engine.embed_for_ingestion(["text"])
        assert result  # fallback returned something
        assert fallback.calls  # fallback was invoked

    @pytest.mark.asyncio
    async def test_fallback_uses_semantic_similarity_task_type(self):
        primary = _StubAdapter(fail=True)
        fallback = _StubAdapter()
        config = _make_config(fallback_enabled=True)
        engine = EmbeddingEngine(config, primary, fallback_adapter=fallback)
        await engine.embed_for_ingestion(["text"])
        assert fallback.calls[0][1] == EmbeddingTaskType.SEMANTIC_SIMILARITY

    @pytest.mark.asyncio
    async def test_no_fallback_adapter_raises_original_exception(self):
        primary = _StubAdapter(fail=True)
        engine = EmbeddingEngine(_make_config(), primary)
        with pytest.raises(RuntimeError, match="stub adapter failure"):
            await engine.embed_for_ingestion(["text"])

    @pytest.mark.asyncio
    async def test_fallback_disabled_in_config_raises(self):
        primary = _StubAdapter(fail=True)
        fallback = _StubAdapter()
        config = _make_config(fallback_enabled=False)
        # Even with a fallback adapter injected, config says disabled
        engine = EmbeddingEngine(config, primary, fallback_adapter=fallback)
        with pytest.raises(RuntimeError):
            await engine.embed_for_ingestion(["text"])

    @pytest.mark.asyncio
    async def test_fallback_not_invoked_when_primary_succeeds(self):
        primary = _StubAdapter()
        fallback = _StubAdapter()
        config = _make_config(fallback_enabled=True)
        engine = EmbeddingEngine(config, primary, fallback_adapter=fallback)
        await engine.embed_for_ingestion(["text"])
        assert fallback.calls == []


# ── circuit breaker integration ───────────────────────────────────────────────


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self):
        adapter = _StubAdapter(fail=True)
        cb = _make_cb_config(failure_threshold=3)
        engine = EmbeddingEngine(_make_config(), adapter, circuit_breaker_config=cb)

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await engine.embed_for_ingestion(["text"])

        with pytest.raises(CircuitBreakerOpenError):
            await engine.embed_for_ingestion(["text"])

    @pytest.mark.asyncio
    async def test_no_breaker_when_config_not_provided(self):
        adapter = _StubAdapter()
        engine = EmbeddingEngine(_make_config(), adapter)
        assert engine._breaker is None
        result = await engine.embed_for_ingestion(["text"])
        assert result

    @pytest.mark.asyncio
    async def test_open_breaker_triggers_fallback_if_configured(self):
        primary = _StubAdapter(fail=True)
        fallback = _StubAdapter()
        cb = _make_cb_config(failure_threshold=1)
        config = _make_config(fallback_enabled=True)
        engine = EmbeddingEngine(
            config,
            primary,
            fallback_adapter=fallback,
            circuit_breaker_config=cb,
        )
        # Both calls route through fallback: first because primary raises,
        # second because the circuit breaker is now OPEN (also an exception
        # caught by the fallback logic).
        result1 = await engine.embed_for_ingestion(["text"])
        result2 = await engine.embed_for_ingestion(["text"])
        assert result1 and result2
        # Fallback must have been invoked for both calls
        assert len(fallback.calls) == 2


# ── _split_batches ────────────────────────────────────────────────────────────


class TestSplitBatches:
    def test_fewer_than_batch_size_is_one_batch(self):
        adapter = _StubAdapter()
        config = _make_config(max_batch_size=10)
        engine = EmbeddingEngine(config, adapter)
        batches = engine._split_batches(["t"] * 5)
        assert batches == [["t"] * 5]

    def test_exact_multiple_gives_equal_batches(self):
        adapter = _StubAdapter()
        config = _make_config(max_batch_size=5)
        engine = EmbeddingEngine(config, adapter)
        batches = engine._split_batches(["t"] * 10)
        assert len(batches) == 2
        assert all(len(b) == 5 for b in batches)

    def test_remainder_gives_smaller_last_batch(self):
        adapter = _StubAdapter()
        config = _make_config(max_batch_size=4)
        engine = EmbeddingEngine(config, adapter)
        batches = engine._split_batches(["t"] * 9)
        assert len(batches) == 3
        assert len(batches[-1]) == 1

    def test_single_text_is_one_batch(self):
        adapter = _StubAdapter()
        config = _make_config(max_batch_size=250)
        engine = EmbeddingEngine(config, adapter)
        batches = engine._split_batches(["only one"])
        assert len(batches) == 1
        assert batches[0] == ["only one"]
