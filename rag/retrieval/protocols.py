"""
Retrieval Layer — shared data types and structural Protocol.

RetrievalResult is the canonical output of every retriever.  All scores are
normalised to [0, 1] before fusion so that dense (cosine) and sparse (BM25)
signals are comparable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class RetrievalResult:
    """Unified result record produced by any retriever."""

    chunk_id: str
    doc_id: str
    content: str
    score: float              # normalised to [0, 1]
    rank: int                 # 0-based rank within the retriever's result list
    retrieval_method: str     # "dense" | "sparse" | "hybrid" | "graph"
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Retriever(Protocol):
    """Structural Protocol satisfied by DenseRetriever, SparseRetriever, etc."""

    async def retrieve(
        self,
        query_embedding: list[float],
        query_text: str,
        *,
        top_k: int,
        allowed_roles: frozenset[str],
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Return up to top_k results, always enforcing RBAC via allowed_roles."""
        ...
