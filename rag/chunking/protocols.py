"""
Chunking protocol — the contract every chunking strategy must satisfy.

Decouples ChunkingEngine from any specific splitting algorithm so adding
a new strategy requires only a new file and a registration call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Chunk:
    """A single unit of text produced by a chunking strategy.

    Attributes:
        content:     The chunk text.
        chunk_index: Position within the document's chunk sequence (0-based).
        metadata:    Arbitrary key/value pairs attached by the strategy or engine.
        parent_id:   For hierarchical child chunks: ``"{doc_id}:parent:{n}"``.
                     None for all other strategies.
        level:       0 = leaf/child chunk; 1 = parent chunk (hierarchical only).
    """

    content: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    level: int = 0


@runtime_checkable
class Chunker(Protocol):
    """Minimal interface a chunking strategy must satisfy."""

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        """Split *text* into chunks.

        Args:
            text:   Input document text.  May be empty — must return ``[]`` in
                    that case.
            doc_id: Stable document identifier used for metadata and hierarchical
                    parent-id construction.

        Returns:
            Ordered list of :class:`Chunk` objects.  Empty list for empty input.
        """
        ...
