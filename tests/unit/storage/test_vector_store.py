"""
Tests for rag.storage.vector_store — AlloyDB pgvector store.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.core.exceptions import StorageError
from rag.core.schemas import DataClassificationLevel, VectorStoreConfig
from rag.storage.protocols import StoredChunk
from rag.storage.vector_store import AlloyDBVectorStore


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_config() -> VectorStoreConfig:
    return VectorStoreConfig()  # injected engine; no connection_string needed


def _make_chunk(
    chunk_id: str = "c1",
    doc_id: str = "d1",
    content: str = "hello world",
    embedding: list[float] | None = None,
) -> StoredChunk:
    return StoredChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        content=content,
        embedding=embedding or [0.1, 0.2, 0.3],
        classification_level=DataClassificationLevel.INTERNAL,
        allowed_roles=frozenset(["reader"]),
    )


def _make_search_row(
    chunk_id: str = "c1",
    doc_id: str = "d1",
    content: str = "hello",
    score: float = 0.9,
) -> MagicMock:
    row = MagicMock()
    row.chunk_id = chunk_id
    row.doc_id = doc_id
    row.content = content
    row.score = score
    row.metadata = {}
    row.classification_level = "INTERNAL"
    row.allowed_roles = []
    return row


def _make_engine(
    *,
    fetchall: list | None = None,
    fetchone: object = None,
    scalar: int | None = 0,
    rowcount: int = 0,
) -> MagicMock:
    """Minimal mock AsyncEngine suitable for all vector store operations."""
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=fetchall or [])
    mock_result.fetchone = MagicMock(return_value=fetchone)
    mock_result.scalar = MagicMock(return_value=scalar)
    mock_result.rowcount = rowcount

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.begin = MagicMock(return_value=mock_ctx)
    mock_engine.connect = MagicMock(return_value=mock_ctx)
    return mock_engine


# ── initialise() ──────────────────────────────────────────────────────────────


class TestInitialise:
    @pytest.mark.asyncio
    async def test_executes_three_ddl_statements(self):
        call_count = [0]
        mock_conn = AsyncMock()

        async def counting_execute(stmt, *_a, **_kw):
            call_count[0] += 1
            return MagicMock()

        mock_conn.execute = counting_execute
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_ctx)

        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.initialise()
        # CREATE TABLE + HNSW index + doc_id index
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_uses_begin_transaction(self):
        engine = _make_engine()
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        await store.initialise()
        engine.begin.assert_called_once()


# ── upsert() ──────────────────────────────────────────────────────────────────


class TestUpsert:
    @pytest.mark.asyncio
    async def test_empty_list_is_noop(self):
        engine = _make_engine()
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        await store.upsert([])
        engine.begin.assert_not_called()

    @pytest.mark.asyncio
    async def test_executes_once_per_chunk(self):
        execute_count = [0]
        mock_conn = AsyncMock()

        async def counting_execute(stmt, params=None):
            execute_count[0] += 1
            return MagicMock()

        mock_conn.execute = counting_execute
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_ctx)

        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.upsert([_make_chunk("c1"), _make_chunk("c2"), _make_chunk("c3")])
        assert execute_count[0] == 3

    @pytest.mark.asyncio
    async def test_embedding_formatted_as_bracketed_csv(self):
        params_captured: list[dict] = []
        mock_conn = AsyncMock()

        async def capture(stmt, params=None):
            if params:
                params_captured.append(params)
            return MagicMock()

        mock_conn.execute = capture
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_ctx)

        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.upsert([_make_chunk(embedding=[1.0, 2.0, 3.0])])
        assert params_captured[0]["embedding"] == "[1.0,2.0,3.0]"

    @pytest.mark.asyncio
    async def test_classification_level_stored_as_value(self):
        params_captured: list[dict] = []
        mock_conn = AsyncMock()

        async def capture(stmt, params=None):
            if params:
                params_captured.append(params)
            return MagicMock()

        mock_conn.execute = capture
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.begin = MagicMock(return_value=mock_ctx)

        chunk = _make_chunk()
        chunk = StoredChunk(
            chunk_id="c1",
            doc_id="d1",
            content="x",
            embedding=[0.1],
            classification_level=DataClassificationLevel.CONFIDENTIAL,
        )
        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.upsert([chunk])
        assert params_captured[0]["classification_level"] == "CONFIDENTIAL"


# ── search() ──────────────────────────────────────────────────────────────────


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_search_results(self):
        rows = [_make_search_row("c1", score=0.9), _make_search_row("c2", score=0.8)]
        engine = _make_engine(fetchall=rows)
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        results = await store.search([0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 2
        assert results[0].chunk_id == "c1"
        assert results[0].score == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(self):
        engine = _make_engine(fetchall=[])
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        results = await store.search([0.1, 0.2], top_k=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_result_fields_mapped_correctly(self):
        row = _make_search_row("chunk_abc", "doc_xyz", "some content", 0.75)
        engine = _make_engine(fetchall=[row])
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        results = await store.search([0.1], top_k=1)
        r = results[0]
        assert r.chunk_id == "chunk_abc"
        assert r.doc_id == "doc_xyz"
        assert r.content == "some content"
        assert r.score == pytest.approx(0.75)
        assert r.classification_level == DataClassificationLevel.INTERNAL

    @pytest.mark.asyncio
    async def test_allowed_roles_injects_rbac_param(self):
        params_captured: list[dict] = []
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_conn = AsyncMock()

        async def capture(stmt, params=None):
            if params:
                params_captured.append(params)
            return mock_result

        mock_conn.execute = capture
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_ctx)

        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.search([0.1], top_k=5, allowed_roles=frozenset(["analyst"]))
        assert params_captured
        assert "allowed_roles" in params_captured[0]
        assert "analyst" in params_captured[0]["allowed_roles"]

    @pytest.mark.asyncio
    async def test_metadata_filters_serialised_as_json(self):
        params_captured: list[dict] = []
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_conn = AsyncMock()

        async def capture(stmt, params=None):
            if params:
                params_captured.append(params)
            return mock_result

        mock_conn.execute = capture
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_ctx)

        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.search([0.1], top_k=5, filters={"source": "policy"})
        assert params_captured
        assert json.loads(params_captured[0]["filters"]) == {"source": "policy"}

    @pytest.mark.asyncio
    async def test_no_filters_no_rbac_param(self):
        params_captured: list[dict] = []
        mock_result = MagicMock()
        mock_result.fetchall = MagicMock(return_value=[])
        mock_conn = AsyncMock()

        async def capture(stmt, params=None):
            if params:
                params_captured.append(params)
            return mock_result

        mock_conn.execute = capture
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect = MagicMock(return_value=mock_ctx)

        store = AlloyDBVectorStore(_make_config(), _engine=mock_engine)
        await store.search([0.1], top_k=5)
        assert "allowed_roles" not in params_captured[0]
        assert "filters" not in params_captured[0]


# ── delete() ──────────────────────────────────────────────────────────────────


class TestDelete:
    @pytest.mark.asyncio
    async def test_returns_rowcount(self):
        engine = _make_engine(rowcount=3)
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        assert await store.delete("doc1") == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_match(self):
        engine = _make_engine(rowcount=0)
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        assert await store.delete("nonexistent") == 0


# ── count() ───────────────────────────────────────────────────────────────────


class TestCount:
    @pytest.mark.asyncio
    async def test_returns_scalar_value(self):
        engine = _make_engine(scalar=42)
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        assert await store.count() == 42

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_table(self):
        engine = _make_engine(scalar=None)
        store = AlloyDBVectorStore(_make_config(), _engine=engine)
        assert await store.count() == 0


# ── _get_engine() guards ──────────────────────────────────────────────────────


class TestGetEngine:
    def test_raises_storage_error_without_connection_string(self):
        store = AlloyDBVectorStore(_make_config())  # no _engine, no connection_string
        with pytest.raises(StorageError):
            store._get_engine()
