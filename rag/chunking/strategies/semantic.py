"""
SemanticChunker — content-aware splitting based on embedding similarity.

Algorithm:
  1. Split text into sentences.
  2. Embed each sentence (using a configurable ``embed_fn``; defaults to a
     lightweight bag-of-chars fallback so no external service is required).
  3. Compute the cosine distance between adjacent sentence embeddings.
  4. Derive a split threshold from the distance distribution using one of three
     strategies: percentile, standard_deviation, or interquartile.
  5. Insert a chunk boundary wherever the distance exceeds the threshold.

The ``embed_fn`` signature matches :meth:`EmbeddingEngine.embed_for_ingestion`
called with a plain list of strings and returning ``list[list[float]]``.
"""

from __future__ import annotations

import math
import re
from typing import Callable

from rag.chunking.protocols import Chunk
from rag.core.schemas import SemanticChunkingConfig

_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(text) if s.strip()]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _bag_of_chars(texts: list[str]) -> list[list[float]]:
    """Fallback embedding: L2-normalised character-frequency vector (dim 128)."""
    result = []
    for text in texts:
        vec = [0.0] * 128
        for ch in text:
            vec[ord(ch) % 128] += 1.0
        mag = math.sqrt(sum(v * v for v in vec)) or 1.0
        result.append([v / mag for v in vec])
    return result


class SemanticChunker:
    """Splits text at semantic topic boundaries detected via embedding similarity."""

    def __init__(
        self,
        config: SemanticChunkingConfig,
        *,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
    ) -> None:
        self._config = config
        self._embed_fn: Callable[[list[str]], list[list[float]]] = embed_fn or _bag_of_chars

    # ------------------------------------------------------------------
    # Chunker protocol
    # ------------------------------------------------------------------

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        if not text.strip():
            return []

        sentences = _split_sentences(text)
        if not sentences:
            return []

        if len(sentences) == 1:
            return [Chunk(content=sentences[0], chunk_index=0, metadata={"doc_id": doc_id})]

        embeddings = self._embed_fn(self._build_buffered(sentences))
        distances = [
            1.0 - _cosine(embeddings[i], embeddings[i + 1])
            for i in range(len(embeddings) - 1)
        ]
        threshold = self._compute_threshold(distances)

        raw_chunks = self._split_at_breakpoints(sentences, distances, threshold)
        return [
            Chunk(content=c, chunk_index=idx, metadata={"doc_id": doc_id})
            for idx, c in enumerate(raw_chunks)
            if c.strip()
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_buffered(self, sentences: list[str]) -> list[str]:
        buf = self._config.buffer_size
        buffered = []
        for i in range(len(sentences)):
            window = sentences[max(0, i - buf) : i + buf + 1]
            buffered.append(" ".join(window))
        return buffered

    def _split_at_breakpoints(
        self,
        sentences: list[str],
        distances: list[float],
        threshold: float,
    ) -> list[str]:
        current: list[str] = [sentences[0]]
        raw_chunks: list[str] = []
        for i, dist in enumerate(distances):
            if dist > threshold:
                raw_chunks.append(" ".join(current))
                current = [sentences[i + 1]]
            else:
                current.append(sentences[i + 1])
        if current:
            raw_chunks.append(" ".join(current))
        return raw_chunks

    def _compute_threshold(self, distances: list[float]) -> float:
        if not distances:
            return 1.0

        bt = self._config.breakpoint_type

        if bt == "percentile":
            pct = self._config.breakpoint_threshold / 100.0
            sorted_d = sorted(distances)
            idx = min(int(len(sorted_d) * pct), len(sorted_d) - 1)
            return sorted_d[idx]

        if bt == "standard_deviation":
            mean = sum(distances) / len(distances)
            variance = sum((d - mean) ** 2 for d in distances) / len(distances)
            std = math.sqrt(variance)
            return mean + std  # one standard deviation above mean

        if bt == "interquartile":
            sorted_d = sorted(distances)
            n = len(sorted_d)
            q1 = sorted_d[max(0, n // 4 - 1)]
            q3 = sorted_d[min(n - 1, 3 * n // 4)]
            iqr = q3 - q1
            return q3 + 1.5 * iqr

        return 0.5  # unreachable given schema validation
