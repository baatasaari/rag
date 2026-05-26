"""
Tests for rag.storage.document_store — AlloyDB document metadata store.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.core.exceptions import StorageError
from rag.core.schemas import DataClassificationLevel, DocumentStoreConfig
from rag.storage.document_store import AlloyDBDocumentStore
from rag.storage.protocols import StoredDocument


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_config() -> DocumentStoreConfig:
    return DocumentStoreConfig()


def _make_doc(
    doc_id: str = "doc1",
    content_hash: str = "abc123",
    classification_level: DataClassificationLevel = DataClassificationLevel.INTERNAL,
) -> StoredDocument:
    return StoredDocument(
        doc_id=doc_id,
        source_uri="gs://bucket/file.pdf",
        title="Test Document",
        content_hash=content_hash,
        classification_level=classification_level,
        allowed_roles=frozenset(["reader"]),
        chunk_ids=["c1", "c2"],
        metadata={"department": "risk"},
    )


def _row_from_doc(doc: StoredDocument) -> MagicMock:
    row = MagicMock()
    row.doc_id = doc.doc_id
    row.source_uri = doc.source_uri
    row.title = doc.title
    row.content_hash = doc.content_hash
    row.classification_level = doc.classification_level.value
    row.allowed_roles = list(doc.allowed_roles)
    row.chunk_ids = list(doc.chunk_ids)
    row.metadata = dict(doc.metadata)
    row.ingested_at = datetime.now(UTC)
    return row


def _make_engine(
    *,
    fetchone: object = None,
    fetchall: list | None = None,
    rowcount: int = 0,
) -> MagicMock:
    mock_result = MagicMock()
    mock_result.fetchone = MagicMock(return_value=fetchone)
    mock_result.fetchall = MagicMock(return_value=fetchall or [])
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

        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.initialise()
        # CREATE TABLE + hash unique index + source_uri index
        assert call_count[0] == 3


# ── put() ─────────────────────────────────────────────────────────────────────


class TestPut:
    @pytest.mark.asyncio
    async def test_uses_write_transaction(self):
        engine = _make_engine()
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        await store.put(_make_doc())
        engine.begin.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_doc_id_and_hash(self):
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

        doc = _make_doc(doc_id="doc42", content_hash="sha256abc")
        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.put(doc)
        assert params_captured
        p = params_captured[0]
        assert p["doc_id"] == "doc42"
        assert p["content_hash"] == "sha256abc"
        assert p["classification_level"] == "INTERNAL"

    @pytest.mark.asyncio
    async def test_serialises_allowed_roles_as_list(self):
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

        doc = _make_doc()
        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.put(doc)
        assert isinstance(params_captured[0]["allowed_roles"], list)


# ── get() ─────────────────────────────────────────────────────────────────────


class TestGet:
    @pytest.mark.asyncio
    async def test_returns_document_when_found(self):
        doc = _make_doc()
        engine = _make_engine(fetchone=_row_from_doc(doc))
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        result = await store.get("doc1")
        assert result is not None
        assert result.doc_id == "doc1"
        assert result.title == "Test Document"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        engine = _make_engine(fetchone=None)
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        assert await store.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_classification_level_deserialised(self):
        doc = _make_doc(classification_level=DataClassificationLevel.RESTRICTED)
        engine = _make_engine(fetchone=_row_from_doc(doc))
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        result = await store.get("doc1")
        assert result is not None
        assert result.classification_level == DataClassificationLevel.RESTRICTED


# ── get_by_hash() ─────────────────────────────────────────────────────────────


class TestGetByHash:
    @pytest.mark.asyncio
    async def test_returns_document_for_known_hash(self):
        doc = _make_doc(content_hash="sha256xxx")
        engine = _make_engine(fetchone=_row_from_doc(doc))
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        result = await store.get_by_hash("sha256xxx")
        assert result is not None
        assert result.content_hash == "sha256xxx"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_hash(self):
        engine = _make_engine(fetchone=None)
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        assert await store.get_by_hash("missing") is None


# ── delete() ──────────────────────────────────────────────────────────────────


class TestDelete:
    @pytest.mark.asyncio
    async def test_returns_true_when_row_deleted(self):
        engine = _make_engine(rowcount=1)
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        assert await store.delete("doc1") is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self):
        engine = _make_engine(rowcount=0)
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        assert await store.delete("missing") is False


# ── list() ────────────────────────────────────────────────────────────────────


class TestList:
    @pytest.mark.asyncio
    async def test_returns_all_documents(self):
        docs = [_make_doc("d1"), _make_doc("d2"), _make_doc("d3")]
        engine = _make_engine(fetchall=[_row_from_doc(d) for d in docs])
        store = AlloyDBDocumentStore(_make_config(), _engine=engine)
        result = await store.list()
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_classification_filter_passed_in_params(self):
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

        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.list(classification_level=DataClassificationLevel.CONFIDENTIAL)
        assert params_captured
        assert params_captured[0]["classification_level"] == "CONFIDENTIAL"

    @pytest.mark.asyncio
    async def test_allowed_roles_filter_passed_in_params(self):
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

        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.list(allowed_roles=frozenset(["admin"]))
        assert params_captured
        assert "admin" in params_captured[0]["allowed_roles"]

    @pytest.mark.asyncio
    async def test_limit_and_offset_passed_in_params(self):
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

        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.list(limit=25, offset=50)
        assert params_captured[0]["limit"] == 25
        assert params_captured[0]["offset"] == 50

    @pytest.mark.asyncio
    async def test_no_extra_params_without_filters(self):
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

        store = AlloyDBDocumentStore(_make_config(), _engine=mock_engine)
        await store.list()
        p = params_captured[0]
        assert "classification_level" not in p
        assert "allowed_roles" not in p


# ── _get_engine() guards ──────────────────────────────────────────────────────


class TestGetEngine:
    def test_raises_storage_error_without_connection_string(self):
        store = AlloyDBDocumentStore(_make_config())
        with pytest.raises(StorageError):
            store._get_engine()
