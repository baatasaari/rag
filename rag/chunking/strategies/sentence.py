"""
SentenceChunker — groups sentences into chunks bounded by min/max sentence counts.

Sentence splitting uses a regex that looks for sentence-ending punctuation
(. ! ?) followed by whitespace — sufficient for English prose without an
external NLP dependency.

Boundary merging rule: if the last chunk has fewer than ``min_sentences``
sentences it is merged into the preceding chunk to avoid orphan micro-chunks.
"""

from __future__ import annotations

import re

from rag.chunking.protocols import Chunk
from rag.core.schemas import SentenceChunkingConfig

_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(text) if s.strip()]


class SentenceChunker:
    """Groups complete sentences into fixed-size windows."""

    def __init__(self, config: SentenceChunkingConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Chunker protocol
    # ------------------------------------------------------------------

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        if not text.strip():
            return []

        sentences = _split_sentences(text)
        if not sentences:
            return []

        # Too few sentences to fill even one window — return as a single chunk.
        if len(sentences) <= self._config.min_sentences:
            return [
                Chunk(
                    content=" ".join(sentences),
                    chunk_index=0,
                    metadata={"doc_id": doc_id},
                )
            ]

        raw_chunks = self._build_windows(sentences)
        raw_chunks = self._merge_orphan(raw_chunks)

        return [
            Chunk(content=content, chunk_index=idx, metadata={"doc_id": doc_id})
            for idx, content in enumerate(raw_chunks)
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_windows(self, sentences: list[str]) -> list[str]:
        max_s = self._config.max_sentences
        return [
            " ".join(sentences[i : i + max_s])
            for i in range(0, len(sentences), max_s)
        ]

    def _merge_orphan(self, chunks: list[str]) -> list[str]:
        """Merge the last chunk into the previous one if it is too short."""
        if len(chunks) < 2:
            return chunks
        last_sents = _split_sentences(chunks[-1])
        if len(last_sents) < self._config.min_sentences:
            chunks[-2] = chunks[-2] + " " + chunks[-1]
            chunks.pop()
        return chunks
