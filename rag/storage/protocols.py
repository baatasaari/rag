"""
Shared protocols and data types for the LBG RAG storage layer.

Every storage backend implements the typed Protocol that matches its role.
Callers depend on the Protocol, not the concrete class — this enables
swapping backends (AlloyDB → Vertex AI Vector Search) with zero pipeline
code changes.

Protocols:
  VectorStore   — upsert / search / delete / count / initialise
  DocumentStore — put / get / delete / list / initialise
  SemanticCache — get / set / invalidate
  GraphStore    — upsert_node / upsert_edge / query / initialise
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from rag.core.schemas import DataClassificationLevel


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------


@dataclass
class StoredChunk:
    """A single chunk stored in the vector store."""

    chunk_id: str
    doc_id: str
    content: str
    embedding: list[float]
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    classification_level: DataClassificationLevel = DataClassificationLevel.INTERNAL
    allowed_roles: frozenset[str] = field(default_factory=frozenset)


@dataclass
class SearchResult:
    """A chunk returned by a similarity search."""

    chunk_id: str
    doc_id: str
    content: str
    score: float  # cosine similarity in [−1, 1]; typically [0, 1]
    metadata: dict[str, Any] = field(default_factory=dict)
    classification_level: DataClassificationLevel = DataClassificationLevel.INTERNAL
    allowed_roles: frozenset[str] = field(default_factory=frozenset)


@dataclass
class StoredDocument:
    """Document-level metadata persisted in the document store."""

    doc_id: str
    source_uri: str
    title: str
    content_hash: str  # SHA-256 hex of raw content — used for dedup
    classification_level: DataClassificationLevel = DataClassificationLevel.INTERNAL
    allowed_roles: frozenset[str] = field(default_factory=frozenset)
    chunk_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CacheEntry:
    """A cached query response stored in the semantic cache."""

    query_hash: str  # hex fingerprint of the query embedding
    response: str
    embedding: list[float]
    ttl_seconds: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of *text*, used for chunk/document dedup."""
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class VectorStore(Protocol):
    """Interface for vector similarity stores (pgvector, Vertex AI, etc.)."""

    async def initialise(self) -> None:
        """Create table + index if they do not already exist.  Idempotent."""
        ...

    async def upsert(self, chunks: list[StoredChunk]) -> None:
        """Insert or update chunks.  Idempotent on chunk_id."""
        ...

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        *,
        filters: dict[str, Any] | None = None,
        allowed_roles: frozenset[str] | None = None,
    ) -> list[SearchResult]:
        """Return the top_k most similar chunks, filtered by metadata and roles."""
        ...

    async def delete(self, doc_id: str) -> int:
        """Delete all chunks for doc_id.  Returns the number of chunks removed."""
        ...

    async def count(self) -> int:
        """Return total number of stored chunk vectors."""
        ...


@runtime_checkable
class DocumentStore(Protocol):
    """Interface for document-metadata stores (AlloyDB, Firestore, etc.)."""

    async def initialise(self) -> None:
        ...

    async def put(self, doc: StoredDocument) -> None:
        """Upsert a document record by doc_id."""
        ...

    async def get(self, doc_id: str) -> StoredDocument | None:
        """Return the document with the given ID, or None if not found."""
        ...

    async def get_by_hash(self, content_hash: str) -> StoredDocument | None:
        """Return the document with the given content hash, or None (for dedup)."""
        ...

    async def delete(self, doc_id: str) -> bool:
        """Delete a document record.  Returns True if a record was deleted."""
        ...

    async def list(
        self,
        *,
        classification_level: DataClassificationLevel | None = None,
        allowed_roles: frozenset[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StoredDocument]:
        ...


@runtime_checkable
class SemanticCache(Protocol):
    """Interface for semantic (vector-similarity) query caches."""

    async def get(self, query_embedding: list[float]) -> CacheEntry | None:
        """Return a cached entry if a sufficiently similar query exists, else None."""
        ...

    async def set(
        self,
        query_embedding: list[float],
        response: str,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Cache *response* against *query_embedding* with an optional TTL."""
        ...

    async def invalidate(self, pattern: str = "*") -> int:
        """Delete cache entries whose key matches *pattern*.  Returns count deleted."""
        ...


@runtime_checkable
class GraphStore(Protocol):
    """Interface for property-graph stores (Neo4j, etc.)."""

    async def initialise(self) -> None:
        ...

    async def upsert_node(self, label: str, properties: dict[str, Any]) -> None:
        """MERGE a node with the given label and properties (keyed by 'id')."""
        ...

    async def upsert_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        *,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """MERGE an edge between two existing nodes."""
        ...

    async def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a raw Cypher query and return rows as dicts."""
        ...
