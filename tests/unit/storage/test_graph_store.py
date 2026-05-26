"""
Tests for rag.storage.graph_store — Neo4j graph store.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.core.exceptions import StorageError
from rag.core.schemas import GraphStoreConfig
from rag.storage.graph_store import Neo4jGraphStore


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_config() -> GraphStoreConfig:
    return GraphStoreConfig()


def _make_driver(*, query_results: list | None = None) -> MagicMock:
    """Return a mock Neo4j AsyncDriver."""
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=query_results or [])

    mock_session = AsyncMock()
    mock_session.run = AsyncMock(return_value=mock_result)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session_ctx)
    mock_driver.close = AsyncMock()
    return mock_driver


def _capture_driver(run_calls: list) -> MagicMock:
    """Return a driver whose session.run records (cypher, params) tuples."""
    mock_result = AsyncMock()
    mock_result.data = AsyncMock(return_value=[])

    mock_session = AsyncMock()

    async def capturing_run(cypher, params=None):
        run_calls.append((cypher, params))
        return mock_result

    mock_session.run = capturing_run

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_ctx)
    mock_driver.close = AsyncMock()
    return mock_driver


# ── initialise() ──────────────────────────────────────────────────────────────


class TestInitialise:
    @pytest.mark.asyncio
    async def test_opens_two_sessions(self):
        driver = _make_driver()
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.initialise()
        assert driver.session.call_count == 2

    @pytest.mark.asyncio
    async def test_creates_document_and_chunk_indexes(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.initialise()
        assert len(run_calls) == 2
        cyphers = [c for c, _ in run_calls]
        assert any("Document" in c for c in cyphers)
        assert any("Chunk" in c for c in cyphers)

    @pytest.mark.asyncio
    async def test_creates_indexes_with_if_not_exists(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.initialise()
        for cypher, _ in run_calls:
            assert "IF NOT EXISTS" in cypher


# ── upsert_node() ─────────────────────────────────────────────────────────────


class TestUpsertNode:
    @pytest.mark.asyncio
    async def test_raises_storage_error_without_id(self):
        driver = _make_driver()
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        with pytest.raises(StorageError):
            await store.upsert_node("Entity", {"name": "Alice"})  # missing 'id'

    @pytest.mark.asyncio
    async def test_merges_with_correct_params(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.upsert_node("Entity", {"id": "e1", "name": "Alice"})
        assert run_calls
        cypher, params = run_calls[0]
        assert "MERGE" in cypher
        assert params["id"] == "e1"

    @pytest.mark.asyncio
    async def test_uses_provided_label(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.upsert_node("Concept", {"id": "c1"})
        assert "Concept" in run_calls[0][0]

    @pytest.mark.asyncio
    async def test_passes_full_properties_as_props_param(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        props = {"id": "e1", "name": "Alice", "weight": 0.5}
        await store.upsert_node("Entity", props)
        _, params = run_calls[0]
        assert params["props"] == props


# ── upsert_edge() ─────────────────────────────────────────────────────────────


class TestUpsertEdge:
    @pytest.mark.asyncio
    async def test_merges_relationship_with_correct_params(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.upsert_edge("e1", "e2", "RELATES_TO")
        assert run_calls
        cypher, params = run_calls[0]
        assert "MERGE" in cypher
        assert "RELATES_TO" in cypher
        assert params["from_id"] == "e1"
        assert params["to_id"] == "e2"

    @pytest.mark.asyncio
    async def test_passes_edge_properties(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.upsert_edge("e1", "e2", "CITES", properties={"weight": 0.9})
        _, params = run_calls[0]
        assert params["props"] == {"weight": 0.9}

    @pytest.mark.asyncio
    async def test_defaults_to_empty_props_when_none(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.upsert_edge("e1", "e2", "LINKS")
        _, params = run_calls[0]
        assert params["props"] == {}


# ── query() ───────────────────────────────────────────────────────────────────


class TestQuery:
    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        records = [{"name": "Alice"}, {"name": "Bob"}]
        driver = _make_driver(query_results=records)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        result = await store.query("MATCH (n) RETURN n.name AS name")
        assert result == [{"name": "Alice"}, {"name": "Bob"}]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_match(self):
        driver = _make_driver(query_results=[])
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        result = await store.query("MATCH (n:Ghost) RETURN n")
        assert result == []

    @pytest.mark.asyncio
    async def test_passes_params_to_session_run(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.query("MATCH (n {id: $id}) RETURN n", {"id": "node1"})
        _, params = run_calls[0]
        assert params == {"id": "node1"}

    @pytest.mark.asyncio
    async def test_defaults_to_empty_params(self):
        run_calls: list = []
        driver = _capture_driver(run_calls)
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.query("MATCH (n) RETURN n")
        _, params = run_calls[0]
        assert params == {}


# ── close() ───────────────────────────────────────────────────────────────────


class TestClose:
    @pytest.mark.asyncio
    async def test_calls_driver_close(self):
        driver = _make_driver()
        store = Neo4jGraphStore(_make_config(), _driver=driver)
        await store.close()
        driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_noop_when_driver_not_initialised(self):
        store = Neo4jGraphStore(_make_config())  # no _driver injected
        await store.close()  # must not raise
