"""
Augmentation Layer — shared data types and structural Protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from rag.core.schemas import CitationMode
from rag.retrieval.protocols import RetrievalResult


@dataclass
class Citation:
    """A single source reference attributed to a retrieval result."""

    index: int                 # 1-based display index: [1], [2] …
    chunk_id: str
    doc_id: str
    source_uri: str            # populated from metadata["source_uri"] when available
    title: str                 # populated from metadata["title"] when available
    page: int | None           # page number if available in metadata
    mode: CitationMode
    snippet: str               # short excerpt (first 120 chars of content)


@dataclass
class AugmentedContext:
    """Fully processed context ready for prompt assembly."""

    query: str
    results: list[RetrievalResult]           # original, ordered retrieval results
    compressed_chunks: list[str]             # compressed/extracted content per result
    citations: list[Citation]                # one Citation per result (mode may be NONE)
    total_chars: int                         # total chars across compressed_chunks
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Compressor(Protocol):
    """Structural Protocol satisfied by all context compressors."""

    async def compress(
        self,
        query: str,
        chunks: list[str],
    ) -> list[str]:
        """Compress each chunk, returning a parallel list of shorter strings."""
        ...
