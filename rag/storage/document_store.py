"""
AlloyDB document-metadata store for the LBG RAG Platform.

Registered as: @register("document_store", "alloydb")

Schema (auto-created by initialise()):
    documents(
        doc_id               TEXT PRIMARY KEY,
        source_uri           TEXT NOT NULL,
        title                TEXT NOT NULL DEFAULT '',
        content_hash         TEXT NOT NULL,         -- SHA-256 for dedup
        classification_level TEXT NOT NULL DEFAULT 'INTERNAL',
        allowed_roles        TEXT[] NOT NULL DEFAULT '{}',
        chunk_ids            TEXT[] NOT NULL DEFAULT '{}',
        metadata             JSONB NOT NULL DEFAULT '{}',
        ingested_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )

content_hash has a UNIQUE index so callers can check for duplicate documents
before ingesting.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from rag.core.exceptions import StorageError
from rag.core.registry import register
from rag.core.schemas import CircuitBreakerConfig, DataClassificationLevel, DocumentStoreConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import record_span
from rag.storage.circuit_breaker import CircuitBreaker
from rag.storage.protocols import StoredDocument

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# SQL templates
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id               TEXT        PRIMARY KEY,
    source_uri           TEXT        NOT NULL,
    title                TEXT        NOT NULL DEFAULT '',
    content_hash         TEXT        NOT NULL,
    classification_level TEXT        NOT NULL DEFAULT 'INTERNAL',
    allowed_roles        TEXT[]      NOT NULL DEFAULT '{{}}',
    chunk_ids            TEXT[]      NOT NULL DEFAULT '{{}}',
    metadata             JSONB       NOT NULL DEFAULT '{{}}',
    ingested_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_HASH_INDEX = (
    "CREATE UNIQUE INDEX IF NOT EXISTS documents_content_hash_idx "
    "ON documents (content_hash)"
)
_CREATE_SOURCE_INDEX = (
    "CREATE INDEX IF NOT EXISTS documents_source_uri_idx ON documents (source_uri)"
)

_UPSERT = """
INSERT INTO documents
    (doc_id, source_uri, title, content_hash, classification_level,
     allowed_roles, chunk_ids, metadata, ingested_at)
VALUES
    (:doc_id, :source_uri, :title, :content_hash, :classification_level,
     :allowed_roles::text[], :chunk_ids::text[], :metadata::jsonb, :ingested_at)
ON CONFLICT (doc_id) DO UPDATE SET
    source_uri           = EXCLUDED.source_uri,
    title                = EXCLUDED.title,
    content_hash         = EXCLUDED.content_hash,
    classification_level = EXCLUDED.classification_level,
    allowed_roles        = EXCLUDED.allowed_roles,
    chunk_ids            = EXCLUDED.chunk_ids,
    metadata             = EXCLUDED.metadata,
    ingested_at          = EXCLUDED.ingested_at
"""

_GET_BY_ID = "SELECT * FROM documents WHERE doc_id = :doc_id"
_GET_BY_HASH = "SELECT * FROM documents WHERE content_hash = :hash"
_DELETE = "DELETE FROM documents WHERE doc_id = :doc_id"

_LIST_BASE = """
SELECT * FROM documents
WHERE 1=1
{where_extra}
ORDER BY ingested_at DESC
LIMIT :limit OFFSET :offset
"""


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


@register("document_store", "alloydb")
class AlloyDBDocumentStore:
    """AlloyDB-backed document metadata store.

    Args:
        config: DocumentStoreConfig from RAGConfig.storage.document_store.
        circuit_breaker_config: Optional circuit breaker configuration.
        _engine: Injected async engine for testing.
    """

    def __init__(
        self,
        config: DocumentStoreConfig,
        *,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        _engine: AsyncEngine | None = None,
    ) -> None:
        self._config = config
        self._engine = _engine
        self._breaker: CircuitBreaker | None = (
            CircuitBreaker("alloydb_document_store", circuit_breaker_config)
            if circuit_breaker_config and circuit_breaker_config.enabled
            else None
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialise(self) -> None:
        """Create documents table and indexes if they don't exist."""
        engine = self._get_engine()
        async with engine.begin() as conn:
            await conn.execute(text(_CREATE_TABLE))
            await conn.execute(text(_CREATE_HASH_INDEX))
            await conn.execute(text(_CREATE_SOURCE_INDEX))
        log.info("document_store.initialised", provider="alloydb")

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def put(self, doc: StoredDocument) -> None:
        """Upsert a document record.  Idempotent on doc_id."""
        with record_span("storage.document_store.put"):
            await self._call(self._do_put(doc))

    async def _do_put(self, doc: StoredDocument) -> None:
        engine = self._get_engine()
        async with engine.begin() as conn:
            await conn.execute(
                text(_UPSERT),
                {
                    "doc_id": doc.doc_id,
                    "source_uri": doc.source_uri,
                    "title": doc.title,
                    "content_hash": doc.content_hash,
                    "classification_level": doc.classification_level.value,
                    "allowed_roles": list(doc.allowed_roles),
                    "chunk_ids": list(doc.chunk_ids),
                    "metadata": json.dumps(doc.metadata),
                    "ingested_at": doc.ingested_at,
                },
            )

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    async def get(self, doc_id: str) -> StoredDocument | None:
        with record_span("storage.document_store.get"):
            return await self._call(self._do_get(doc_id))

    async def _do_get(self, doc_id: str) -> StoredDocument | None:
        engine = self._get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text(_GET_BY_ID), {"doc_id": doc_id})
            row = result.fetchone()
        return _row_to_doc(row) if row else None

    async def get_by_hash(self, content_hash: str) -> StoredDocument | None:
        """Return the document with the given SHA-256 content hash (for dedup)."""
        engine = self._get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text(_GET_BY_HASH), {"hash": content_hash})
            row = result.fetchone()
        return _row_to_doc(row) if row else None

    async def delete(self, doc_id: str) -> bool:
        with record_span("storage.document_store.delete"):
            return await self._call(self._do_delete(doc_id))

    async def _do_delete(self, doc_id: str) -> bool:
        engine = self._get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(_DELETE), {"doc_id": doc_id})
            return result.rowcount > 0  # type: ignore[return-value]

    async def list(
        self,
        *,
        classification_level: DataClassificationLevel | None = None,
        allowed_roles: frozenset[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredDocument]:
        with record_span("storage.document_store.list"):
            return await self._call(
                self._do_list(
                    classification_level=classification_level,
                    allowed_roles=allowed_roles,
                    limit=limit,
                    offset=offset,
                )
            )

    async def _do_list(
        self,
        *,
        classification_level: DataClassificationLevel | None,
        allowed_roles: frozenset[str] | None,
        limit: int,
        offset: int,
    ) -> list[StoredDocument]:
        where_clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if classification_level is not None:
            where_clauses.append("AND classification_level = :classification_level")
            params["classification_level"] = classification_level.value

        if allowed_roles is not None:
            where_clauses.append(
                "AND (allowed_roles = '{}' OR allowed_roles && :allowed_roles::text[])"
            )
            params["allowed_roles"] = list(allowed_roles)

        sql = text(_LIST_BASE.format(where_extra="\n".join(where_clauses)))
        engine = self._get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(sql, params)
            rows = result.fetchall()
        return [_row_to_doc(row) for row in rows]  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_engine(self) -> AsyncEngine:
        if self._engine is None:
            if self._config.connection_string is None:
                raise StorageError(
                    "storage.document_store.connection_string is not set.",
                    store_type="alloydb",
                )
            conn_str = self._config.connection_string.get_secret_value()
            self._engine = create_async_engine(
                conn_str,
                pool_size=self._config.pool_size,
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


def _row_to_doc(row: Any) -> StoredDocument:
    return StoredDocument(
        doc_id=row.doc_id,
        source_uri=row.source_uri,
        title=row.title,
        content_hash=row.content_hash,
        classification_level=DataClassificationLevel(row.classification_level),
        allowed_roles=frozenset(row.allowed_roles or []),
        chunk_ids=list(row.chunk_ids or []),
        metadata=dict(row.metadata) if row.metadata else {},
        ingested_at=row.ingested_at
        if isinstance(row.ingested_at, datetime)
        else datetime.fromisoformat(str(row.ingested_at)).replace(tzinfo=UTC),
    )
