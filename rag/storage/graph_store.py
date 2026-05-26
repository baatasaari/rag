"""
Neo4j graph store for the LBG RAG Platform.

Registered as: @register("graph_store", "neo4j")

Used by Graph RAG and RAPTOR patterns to persist entity/concept graphs and
chunk-to-chunk relationships.

Initialise creates indexes on:
  (:Document {doc_id})  — for fast document-level lookups
  (:Chunk    {chunk_id}) — for fast chunk-level lookups

All mutations use MERGE to remain idempotent (safe for re-ingestion).
"""

from __future__ import annotations

from typing import Any

from rag.core.exceptions import StorageError
from rag.core.registry import register
from rag.core.schemas import CircuitBreakerConfig, GraphStoreConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import record_span
from rag.storage.circuit_breaker import CircuitBreaker

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Cypher templates
# ---------------------------------------------------------------------------

_CREATE_DOC_INDEX = (
    "CREATE INDEX document_doc_id IF NOT EXISTS FOR (n:Document) ON (n.doc_id)"
)
_CREATE_CHUNK_INDEX = (
    "CREATE INDEX chunk_chunk_id IF NOT EXISTS FOR (n:Chunk) ON (n.chunk_id)"
)

_MERGE_NODE = "MERGE (n:{label} {{id: $id}}) SET n += $props RETURN n"

_MERGE_EDGE = (
    "MATCH (a {{id: $from_id}}), (b {{id: $to_id}}) "
    "MERGE (a)-[r:{rel_type}]->(b) SET r += $props RETURN r"
)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


@register("graph_store", "neo4j")
class Neo4jGraphStore:
    """Neo4j-backed graph store using the official async Python driver.

    Args:
        config: GraphStoreConfig from RAGConfig.storage.graph_store.
        circuit_breaker_config: Optional circuit breaker config.
        _driver: Injected Neo4j AsyncDriver (for testing).
    """

    def __init__(
        self,
        config: GraphStoreConfig,
        *,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        _driver: Any = None,
    ) -> None:
        self._config = config
        self._driver = _driver  # None → lazy-init
        self._breaker: CircuitBreaker | None = (
            CircuitBreaker("neo4j", circuit_breaker_config)
            if circuit_breaker_config and circuit_breaker_config.enabled
            else None
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialise(self) -> None:
        """Create indexes on Document and Chunk nodes.  Idempotent."""
        await self._run(_CREATE_DOC_INDEX)
        await self._run(_CREATE_CHUNK_INDEX)
        log.info("graph_store.initialised", provider="neo4j")

    async def close(self) -> None:
        """Close the driver connection pool."""
        if self._driver is not None:
            await self._driver.close()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def upsert_node(self, label: str, properties: dict[str, Any]) -> None:
        """MERGE a node with the given label, keyed by 'id' in *properties*.

        Raises:
            StorageError: if 'id' is not present in *properties*.
        """
        node_id = properties.get("id")
        if not node_id:
            raise StorageError(
                "upsert_node requires 'id' in properties.",
                store_type="neo4j",
            )
        with record_span(f"storage.graph_store.upsert_node.{label}"):
            await self._call(
                self._run(
                    _MERGE_NODE.format(label=label),
                    {"id": node_id, "props": properties},
                )
            )

    async def upsert_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        *,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """MERGE an edge between two existing nodes."""
        with record_span(f"storage.graph_store.upsert_edge.{rel_type}"):
            await self._call(
                self._run(
                    _MERGE_EDGE.format(rel_type=rel_type),
                    {
                        "from_id": from_id,
                        "to_id": to_id,
                        "props": properties or {},
                    },
                )
            )

    # ------------------------------------------------------------------
    # Query path
    # ------------------------------------------------------------------

    async def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a raw Cypher query and return results as dicts."""
        with record_span("storage.graph_store.query"):
            return await self._call(self._do_query(cypher, params or {}))

    async def _do_query(
        self, cypher: str, params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        driver = self._get_driver()
        async with driver.session(database=self._config.database) as session:
            result = await session.run(cypher, params)
            records = await result.data()
            return [dict(r) for r in records]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run(self, cypher: str, params: dict[str, Any] | None = None) -> None:
        """Execute a Cypher statement, discarding results."""
        driver = self._get_driver()
        async with driver.session(database=self._config.database) as session:
            await session.run(cypher, params or {})

    def _get_driver(self) -> Any:
        if self._driver is not None:
            return self._driver
        try:
            from neo4j import AsyncGraphDatabase
        except ImportError as exc:
            raise RuntimeError(
                "neo4j package is required. Install with: pip install neo4j"
            ) from exc

        if not self._config.uri:
            raise StorageError("storage.graph_store.uri is not set.", store_type="neo4j")
        if not self._config.username or not self._config.password:
            raise StorageError(
                "storage.graph_store.username and password are required.",
                store_type="neo4j",
            )

        uri = self._config.uri.get_secret_value()
        password = self._config.password.get_secret_value()

        self._driver = AsyncGraphDatabase.driver(
            uri,
            auth=(self._config.username, password),
            max_connection_pool_size=self._config.max_connection_pool_size,
        )
        return self._driver

    async def _call(self, coro: Any) -> Any:
        if self._breaker:
            return await self._breaker.call(coro)
        return await coro
