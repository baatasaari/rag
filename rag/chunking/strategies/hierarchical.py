"""
HierarchicalChunker — produces interleaved parent and child chunks.

Parent chunks (level=1) span ``parent_chunk_size`` words each.  Child chunks
(level=0) are sub-windows of each parent, sized at ``child_chunk_size`` words
with ``overlap`` word overlap between adjacent children.

Relationship encoding:
  - parent.parent_id  = None
  - child.parent_id   = "{doc_id}:parent:{parent_index}"

This structure powers small-to-big retrieval: the retriever scores children
(compact, precise) and the LLM receives the parent (rich context).
"""

from __future__ import annotations

from rag.chunking.protocols import Chunk
from rag.core.schemas import HierarchicalChunkingConfig


class HierarchicalChunker:
    """Produces interleaved parent (level=1) and child (level=0) chunks."""

    def __init__(self, config: HierarchicalChunkingConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Chunker protocol
    # ------------------------------------------------------------------

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        if not text.strip():
            return []

        words = text.split()
        if not words:
            return []

        cfg = self._config
        p_size = cfg.parent_chunk_size
        c_size = cfg.child_chunk_size
        c_step = max(1, c_size - cfg.overlap)

        chunks: list[Chunk] = []
        chunk_idx = 0

        for p_idx, p_start in enumerate(range(0, len(words), p_size)):
            parent_words = words[p_start : p_start + p_size]
            parent_content = " ".join(parent_words)
            parent_id = f"{doc_id}:parent:{p_idx}"

            chunks.append(
                Chunk(
                    content=parent_content,
                    chunk_index=chunk_idx,
                    metadata={"doc_id": doc_id, "parent_index": p_idx},
                    parent_id=None,
                    level=1,
                )
            )
            chunk_idx += 1

            for c_start in range(0, len(parent_words), c_step):
                child_words = parent_words[c_start : c_start + c_size]
                if not child_words:
                    break
                chunks.append(
                    Chunk(
                        content=" ".join(child_words),
                        chunk_index=chunk_idx,
                        metadata={"doc_id": doc_id, "parent_index": p_idx},
                        parent_id=parent_id,
                        level=0,
                    )
                )
                chunk_idx += 1

        return chunks
