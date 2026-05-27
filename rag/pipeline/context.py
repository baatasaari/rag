"""
QueryContext — per-request context passed to RAGPipeline.query().

Immutable after construction.  RBAC is enforced via allowed_roles, which must
reflect the authenticated user's actual roles — the pipeline never grants
access beyond what is in this set.

Fields:
  query          Raw user query string (PII sanitisation is the caller's
                 responsibility — use rag.security.pii before reaching here).
  user_id        Authenticated user identifier (for audit logging only).
  allowed_roles  Frozenset of RBAC roles the user holds.  Passed verbatim to
                 the vector store's server-side filter.
  query_id       Unique request ID.  Auto-generated if not supplied.
  session_id     Optional conversation session identifier.
  filters        Server-side metadata filters (e.g. doc_type, region).
  top_k          Per-request override of config.retrieval.top_k.
  stream         If True, callers should use RAGPipeline.stream_query().
  metadata       Arbitrary caller-supplied metadata (logged, not used in RAG).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class QueryContext:
    """Immutable per-request context for a single RAG query."""

    query: str
    user_id: str
    allowed_roles: frozenset[str]
    query_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str | None = None
    filters: dict[str, Any] | None = None
    top_k: int | None = None
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
