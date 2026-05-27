"""
RecursiveChunker — hierarchical separator-based splitting with overlap.

Mirrors the LangChain RecursiveCharacterTextSplitter algorithm:

1. Try each separator in order; use the first one found in the text.
2. Split the text by that separator into sub-strings.
3. For any sub-string still exceeding chunk_size, recurse with the remaining
   (lower-priority) separators.
4. Merge neighbouring sub-strings back up towards chunk_size, carrying
   ``overlap`` characters of context from the previous chunk.
5. If no separator is found at all, hard-split by character index.

All size measurements are in *characters* (chunk_size, overlap).
"""

from __future__ import annotations

from rag.chunking.protocols import Chunk
from rag.core.schemas import RecursiveChunkingConfig


class RecursiveChunker:
    """Separator-recursive character-level chunker."""

    def __init__(self, config: RecursiveChunkingConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Chunker protocol
    # ------------------------------------------------------------------

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        if not text.strip():
            return []

        raw = self._split(text, list(self._config.separators))
        return [
            Chunk(content=content, chunk_index=idx, metadata={"doc_id": doc_id})
            for idx, content in enumerate(raw)
            if content.strip()
        ]

    # ------------------------------------------------------------------
    # Recursive splitting
    # ------------------------------------------------------------------

    def _split(self, text: str, separators: list[str]) -> list[str]:
        size = self._config.chunk_size

        if len(text) <= size:
            return [text]

        # Find the first separator present in the text.
        sep: str | None = None
        remaining_seps: list[str] = []
        for i, s in enumerate(separators):
            if s in text:
                sep = s
                remaining_seps = separators[i + 1 :]
                break

        if sep is None:
            return self._hard_split(text)

        # Split and recursively chunk any oversized piece.
        good: list[str] = []
        for piece in text.split(sep):
            if not piece:
                continue
            if len(piece) > size:
                good.extend(self._split(piece, remaining_seps))
            else:
                good.append(piece)

        return self._merge(good, sep)

    def _hard_split(self, text: str) -> list[str]:
        size = self._config.chunk_size
        step = max(1, size - self._config.overlap)
        return [text[i : i + size] for i in range(0, len(text), step) if text[i : i + size]]

    def _merge(self, splits: list[str], sep: str) -> list[str]:
        """Merge small splits back together, respecting chunk_size and overlap."""
        size = self._config.chunk_size
        overlap = self._config.overlap
        sep_len = len(sep)

        result: list[str] = []
        bucket: list[str] = []
        bucket_len = 0

        for s in splits:
            s_len = len(s)
            added = s_len + (sep_len if bucket else 0)

            if bucket and bucket_len + added > size:
                result.append(sep.join(bucket))
                # Keep a suffix of bucket worth ≤ overlap chars.
                if overlap > 0:
                    tail: list[str] = []
                    tail_len = 0
                    for p in reversed(bucket):
                        extra = len(p) + (sep_len if tail else 0)
                        if tail_len + extra > overlap:
                            break
                        tail.insert(0, p)
                        tail_len += extra
                    bucket = tail
                    bucket_len = tail_len
                else:
                    bucket = []
                    bucket_len = 0

            bucket.append(s)
            bucket_len += s_len + (sep_len if len(bucket) > 1 else 0)

        if bucket:
            result.append(sep.join(bucket))

        return result
