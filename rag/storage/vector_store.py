"""
AlloyDB + pgvector vector store for the LBG RAG Platform.

Registered as: @register("vector_store", "alloydb_pgvector")

Schema (auto-created by initialise()):
    chunks(
        chunk_id          TEXT PRIMARY KEY,
        doc_id            TEXT NOT NULL,
        content           TEXT NOT NULL,
        embedding         vector(<dimensions>),
        chunk_index       INTEGER NOT NULL DEFAULT 0,
        metadata          JSONB NOT NULL DEFAULT '{}',
        classification_level TEXT NOT NULL DEFAULT 'INTERNAL',
        allowed_roles     TEXT[] NOT NULL DEFAULT '{}',
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )

HNSW index on embedding using cosine distance (configurable m, ef_construction).
RBAC filter: allowed_roles && $user_roles appended to every search query when
allowed_roles is supplied by the retrieval layer.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rag.core.exceptions import StorageError
from rag.core.registry import register
from rag.core.schemas import CircuitBreakerConfig, VectorStoreConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.storage.circuit_breaker import CircuitBreaker
from rag.storage.protocols import SearchResult, StoredChunk

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL templates
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id          TEXT        PRIMARY KEY,
    doc_id            TEXT        NOT NULL,
    content           TEXT        NOT NULL,
    embedding         vector({dimensions}),
    chunk_index       INTEGER     NOT NULL DEFAULT 0,
    metadata          JSONB       NOT NULL DEFAULT '{{}}',
    classification_level TEXT     NOT NULL DEFAULT 'INTERNAL',
    allowed_roles     TEXT[]      NOT NULL DEFAULT '{{}}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_HNSW_INDEX = """
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
ON chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = {m}, ef_construction = {ef_construction})
"""

_CREATE_DOC_ID_INDEX = "CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id)"

_UPSERT_CHUNK = """
INSERT INTO chunks
    (chunk_id, doc_id, content, embedding, chunk_index, metadata,
     classification_level, allowed_roles)
VALUES
    (:chunk_id, :doc_id, :content, :embedding::vector, :chunk_index,
     :metadata::jsonb, :classification_level, :allowed_roles::text[])
ON CONFLICT (chunk_id) DO UPDATE SET
    doc_id             = EXCLUDED.doc_id,
    content            = EXCLUDED.content,
    embedding          = EXCLUDED.embedding,
    chunk_index        = EXCLUDED.chunk_index,
    metadata           = EXCLUDED.metadata,
    classification_level = EXCLUDED.classification_level,
    allowed_roles      = EXCLUDED.allowed_roles
"""

_SEARCH_BASE = """
SELECT chunk_id, doc_id, content, metadata, classification_level, allowed_roles,
       1 - (embedding <=> :embedding::vector) AS score
FROM chunks
WHERE embedding IS NOT NULL
{where_extra}
ORDER BY embedding <=> :embedding::vector
LIMIT :top_k
"""

_DELETE_BY_DOC = "DELETE FROM chunks WHERE doc_id = :doc_id"
_COUNT = "SELECT COUNT(*) FROM chunks"


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


@register("vector_store", "alloydb_pgvector")
class AlloyDBVectorStore:
    """pgvector-backed vector store on AlloyDB Omni / Cloud AlloyDB.

    Args:
        config: VectorStoreConfig from RAGConfig.storage.vector_store.
        circuit_breaker_config: Optional circuit breaker configuration.
        _engine: Injected SQLAlchemy async engine (for testing).
    """

    def __init__(
        self,
        config: VectorStoreConfig,
        *,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        _engine: AsyncEngine | None = None,
    ) -> None:
        self._config = config
        self._engine = _engine  # None → created lazily on first use
        self._breaker: CircuitBreaker | None = (
            CircuitBreaker("alloydb_pgvector", circuit_breaker_config)
            if circuit_breaker_config and circuit_breaker_config.enabled
            else None
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialise(self) -> None:
        """Create the chunks table and HNSW index if they don't exist.

        Safe to call multiple times (all statements use IF NOT EXISTS).
        """
        dims = self._config.dimensions
        hnsw = self._config.index.hnsw
        engine = self._get_engine()

        async with engine.begin() as conn:
            await conn.execute(text(_CREATE_TABLE.format(dimensions=dims)))
            await conn.execute(
                text(
                    _CREATE_HNSW_INDEX.format(
                        m=hnsw.m, ef_construction=hnsw.ef_construction
                    )
                )
            )
            await conn.execute(text(_CREATE_DOC_ID_INDEX))

        log.info(
            "vector_store.initialised",
            provider="alloydb_pgvector",
            dimensions=dims,
            hnsw_m=hnsw.m,
        )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def upsert(self, chunks: list[StoredChunk]) -> None:
        """Upsert a batch of chunks.  Idempotent on chunk_id."""
        if not chunks:
            return

        with record_span(
            "storage.vector_store.upsert",
            **{RAGAttributes.CHUNK_COUNT: len(chunks)},
        ):
            await self._call(self._do_upsert(chunks))

    async def _do_upsert(self, chunks: list[StoredChunk]) -> None:
        engine = self._get_engine()
        async with engine.begin() as conn:
            for chunk in chunks:
                embedding_str = f"[{','.join(str(v) for v in chunk.embedding)}]"
                await conn.execute(
                    text(_UPSERT_CHUNK),
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "content": chunk.content,
                        "embedding": embedding_str,
                        "chunk_index": chunk.chunk_index,
                        "metadata": json.dumps(chunk.metadata),
                        "classification_level": chunk.classification_level.value,
                        "allowed_roles": list(chunk.allowed_roles),
                    },
                )

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        *,
        filters: dict[str, Any] | None = None,
        allowed_roles: frozenset[str] | None = None,
    ) -> list[SearchResult]:
        """Similarity search with optional RBAC and metadata filters."""
        with record_span(
            "storage.vector_store.search",
            **{
                RAGAttributes.RETRIEVAL_TOP_K: top_k,
                RAGAttributes.RETRIEVAL_STRATEGY: "vector",
            },
        ) as span:
            results = await self._call(
                self._do_search(embedding, top_k, filters=filters, allowed_roles=allowed_roles)
            )
            span.set_attribute(RAGAttributes.RETRIEVAL_CHUNK_COUNT, len(results))
            return results

    async def _do_search(
        self,
        embedding: list[float],
        top_k: int,
        *,
        filters: dict[str, Any] | None,
        allowed_roles: frozenset[str] | None,
    ) -> list[SearchResult]:
        where_clauses: list[str] = []
        params: dict[str, Any] = {
            "embedding": f"[{','.join(str(v) for v in embedding)}]",
            "top_k": top_k,
        }

        if allowed_roles is not None:
            where_clauses.append(
                "(allowed_roles = '{}' OR allowed_roles && :allowed_roles::text[])"
            )
            params["allowed_roles"] = list(allowed_roles)

        if filters:
            where_clauses.append("metadata @> :filters::jsonb")
            params["filters"] = json.dumps(filters)

        where_extra = ("AND " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = text(_SEARCH_BASE.format(where_extra=where_extra))

        engine = self._get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(sql, params)
            rows = result.fetchall()

        return [_row_to_search_result(row) for row in rows]

    async def delete(self, doc_id: str) -> int:
        """Delete all chunks for a document.  Returns count deleted."""
        with record_span("storage.vector_store.delete"):
            return await self._call(self._do_delete(doc_id))

    async def _do_delete(self, doc_id: str) -> int:
        engine = self._get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(_DELETE_BY_DOC), {"doc_id": doc_id})
            return result.rowcount  # type: ignore[return-value]

    async def count(self) -> int:
        engine = self._get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text(_COUNT))
            return result.scalar() or 0  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_engine(self) -> AsyncEngine:
        if self._engine is None:
            if self._config.connection_string is None:
                raise StorageError(
                    "storage.vector_store.connection_string is not set.",
                    store_type="alloydb_pgvector",
                )
            conn_str = self._config.connection_string.get_secret_value()
            self._engine = create_async_engine(
                conn_str,
                pool_size=self._config.pool_size,
                max_overflow=self._config.max_overflow,
                echo=False,
            )
        return self._engine

    async def _call(self, coro: Any) -> Any:
        if self._breaker:
            return await self._breaker.call(coro)
        return await coro


# ---------------------------------------------------------------------------
# Row → dataclass conversion
# ---------------------------------------------------------------------------


def _row_to_search_result(row: Any) -> SearchResult:
    from rag.core.schemas import DataClassificationLevel

    return SearchResult(
        chunk_id=row.chunk_id,
        doc_id=row.doc_id,
        content=row.content,
        score=float(row.score),
        metadata=dict(row.metadata) if row.metadata else {},
        classification_level=DataClassificationLevel(
            row.classification_level
        ),
        allowed_roles=frozenset(row.allowed_roles or []),
    )
