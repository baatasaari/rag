"""
Tests for rag.ingestion.pipeline — IngestionPipeline orchestration.

Tests cover: happy path, duplicate skip, no-chunks abort, RESTRICTED abort,
soft-stage failure isolation, and stage ordering.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.chunking.protocols import Chunk
from rag.core.schemas import DataClassificationLevel
from rag.ingestion.pipeline import IngestionPipeline


# ── helpers ───────────────────────────────────────────────────────────────────


def _chunk(content: str, idx: int = 0) -> Chunk:
    return Chunk(content=content, chunk_index=idx, metadata={"doc_id": "test"})


def _make_pipeline(
    *,
    doc_store_existing=None,
    chunks=None,
    embeddings=None,
    reject_restricted=True,
) -> tuple[IngestionPipeline, dict]:
    """Build a pipeline with fully mocked stores and engines."""
    if chunks is None:
        chunks = [_chunk("chunk one content here and more", 0)]
    if embeddings is None:
        embeddings = [[0.1, 0.2] for _ in chunks]

    config = MagicMock()
    config.security.pii_detection.reject_restricted_data = reject_restricted
    config.ingestion.cleaner.min_content_length = 10

    chunking_engine = MagicMock()
    chunking_engine.chunk.return_value = chunks

    embedding_engine = AsyncMock()
    embedding_engine.embed_for_ingestion = AsyncMock(return_value=embeddings)

    vector_store = AsyncMock()
    document_store = AsyncMock()
    document_store.get_by_hash = AsyncMock(return_value=doc_store_existing)
    document_store.put = AsyncMock()

    graph_store = AsyncMock()
    cache = AsyncMock()
    cache.invalidate = AsyncMock(return_value=0)
    audit_logger = AsyncMock()
    audit_logger.log_event = AsyncMock()

    pipeline = IngestionPipeline(
        config=config,
        chunking_engine=chunking_engine,
        embedding_engine=embedding_engine,
        vector_store=vector_store,
        document_store=document_store,
        graph_store=graph_store,
        cache=cache,
        audit_logger=audit_logger,
    )

    mocks = {
        "config": config,
        "chunking_engine": chunking_engine,
        "embedding_engine": embedding_engine,
        "vector_store": vector_store,
        "document_store": document_store,
        "graph_store": graph_store,
        "cache": cache,
        "audit_logger": audit_logger,
    }
    return pipeline, mocks


_SAMPLE_CONTENT = b"Hello world. This is a test document for the LBG RAG platform."


# ── happy path ────────────────────────────────────────────────────────────────


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_returns_ingestion_context(self):
        pipeline, _ = _make_pipeline()
        ctx = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_all_main_stages_completed(self):
        pipeline, _ = _make_pipeline()
        ctx = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        assert "validate" in ctx.completed_stages
        assert "extract" in ctx.completed_stages
        assert "chunk" in ctx.completed_stages
        assert "embed" in ctx.completed_stages
        assert "upsert_vectors" in ctx.completed_stages
        assert "upsert_document" in ctx.completed_stages
        assert "audit" in ctx.completed_stages

    @pytest.mark.asyncio
    async def test_not_aborted_on_clean_run(self):
        pipeline, _ = _make_pipeline()
        ctx = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        assert not ctx.should_abort

    @pytest.mark.asyncio
    async def test_doc_id_is_deterministic(self):
        pipeline, _ = _make_pipeline()
        ctx1 = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        ctx2 = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        assert ctx1.doc_id == ctx2.doc_id

    @pytest.mark.asyncio
    async def test_vector_store_upsert_called(self):
        pipeline, mocks = _make_pipeline()
        await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        mocks["vector_store"].upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_store_put_called(self):
        pipeline, mocks = _make_pipeline()
        await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        mocks["document_store"].put.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_always_called(self):
        pipeline, mocks = _make_pipeline()
        await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        mocks["audit_logger"].log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_in_context(self):
        chunks = [_chunk("word " * 15, i) for i in range(3)]
        pipeline, _ = _make_pipeline(chunks=chunks, embeddings=[[0.1] for _ in chunks])
        ctx = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        assert len(ctx.chunks) == 3

    @pytest.mark.asyncio
    async def test_source_uri_stored_in_context(self):
        pipeline, _ = _make_pipeline()
        ctx = await pipeline.run("gs://my-bucket/report.txt", _SAMPLE_CONTENT)
        assert ctx.source_uri == "gs://my-bucket/report.txt"


# ── duplicate skip ────────────────────────────────────────────────────────────


class TestDuplicateSkip:
    @pytest.mark.asyncio
    async def test_duplicate_sets_is_duplicate(self):
        existing = MagicMock()
        existing.doc_id = "old-doc"
        pipeline, _ = _make_pipeline(doc_store_existing=existing)
        ctx = await pipeline.run("gs://bucket/dup.txt", _SAMPLE_CONTENT)
        assert ctx.is_duplicate is True

    @pytest.mark.asyncio
    async def test_duplicate_aborts_pipeline(self):
        existing = MagicMock()
        existing.doc_id = "old-doc"
        pipeline, _ = _make_pipeline(doc_store_existing=existing)
        ctx = await pipeline.run("gs://bucket/dup.txt", _SAMPLE_CONTENT)
        assert ctx.should_abort is True

    @pytest.mark.asyncio
    async def test_duplicate_skips_embedding(self):
        existing = MagicMock()
        existing.doc_id = "old-doc"
        pipeline, mocks = _make_pipeline(doc_store_existing=existing)
        await pipeline.run("gs://bucket/dup.txt", _SAMPLE_CONTENT)
        mocks["embedding_engine"].embed_for_ingestion.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_skips_vector_store(self):
        existing = MagicMock()
        existing.doc_id = "old-doc"
        pipeline, mocks = _make_pipeline(doc_store_existing=existing)
        await pipeline.run("gs://bucket/dup.txt", _SAMPLE_CONTENT)
        mocks["vector_store"].upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_still_audited(self):
        existing = MagicMock()
        existing.doc_id = "old-doc"
        pipeline, mocks = _make_pipeline(doc_store_existing=existing)
        await pipeline.run("gs://bucket/dup.txt", _SAMPLE_CONTENT)
        mocks["audit_logger"].log_event.assert_called_once()


# ── no-chunks abort ───────────────────────────────────────────────────────────


class TestNoChunksAbort:
    @pytest.mark.asyncio
    async def test_empty_chunks_aborts(self):
        pipeline, _ = _make_pipeline(chunks=[], embeddings=[])
        ctx = await pipeline.run("gs://bucket/empty.txt", _SAMPLE_CONTENT)
        assert ctx.should_abort is True

    @pytest.mark.asyncio
    async def test_all_too_short_chunks_aborts(self):
        # All chunks are too short to pass validate_chunks (min=10 chars)
        tiny = [_chunk("hi", 0)]
        pipeline, _ = _make_pipeline(chunks=tiny, embeddings=[[0.1]])
        ctx = await pipeline.run("gs://bucket/short.txt", _SAMPLE_CONTENT)
        assert ctx.should_abort is True

    @pytest.mark.asyncio
    async def test_no_chunks_skips_embedding(self):
        pipeline, mocks = _make_pipeline(chunks=[], embeddings=[])
        await pipeline.run("gs://bucket/empty.txt", _SAMPLE_CONTENT)
        mocks["embedding_engine"].embed_for_ingestion.assert_not_called()


# ── RESTRICTED abort ──────────────────────────────────────────────────────────


class TestRestrictedAbort:
    @pytest.mark.asyncio
    async def test_restricted_doc_aborted(self):
        # Use text containing "restricted" keyword to trigger classification.
        content = b"RESTRICTED: board only document for senior management."
        pipeline, _ = _make_pipeline(reject_restricted=True)
        ctx = await pipeline.run("gs://bucket/restricted.txt", content)
        assert ctx.should_abort is True

    @pytest.mark.asyncio
    async def test_restricted_skips_persistence(self):
        content = b"RESTRICTED: board only document for senior management."
        pipeline, mocks = _make_pipeline(reject_restricted=True)
        await pipeline.run("gs://bucket/restricted.txt", content)
        mocks["vector_store"].upsert.assert_not_called()


# ── soft stage isolation ──────────────────────────────────────────────────────


class TestSoftStageIsolation:
    @pytest.mark.asyncio
    async def test_graph_store_failure_does_not_abort(self):
        pipeline, mocks = _make_pipeline()
        mocks["graph_store"].upsert_node = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        ctx = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        # Pipeline should still complete — graph is soft.
        assert not ctx.should_abort
        assert "upsert_graph" in ctx.stage_errors

    @pytest.mark.asyncio
    async def test_cache_failure_does_not_abort(self):
        pipeline, mocks = _make_pipeline()
        mocks["cache"].invalidate = AsyncMock(side_effect=RuntimeError("Redis down"))
        ctx = await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        # Cache handles its own error internally — pipeline continues unaffected.
        assert not ctx.should_abort
        # invalidate_cache still marks itself done (handled inside s14_cache)
        assert "invalidate_cache" in ctx.completed_stages

    @pytest.mark.asyncio
    async def test_vector_store_upserted_despite_graph_failure(self):
        pipeline, mocks = _make_pipeline()
        mocks["graph_store"].upsert_node = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        mocks["vector_store"].upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_called_despite_graph_failure(self):
        pipeline, mocks = _make_pipeline()
        mocks["graph_store"].upsert_node = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        await pipeline.run("gs://bucket/doc.txt", _SAMPLE_CONTENT)
        mocks["audit_logger"].log_event.assert_called_once()
