"""
FixedChunker — splits text into fixed-size windows with configurable overlap.

Supports three unit modes:
  - chars:  character-level windows (good for code or non-whitespace languages)
  - words:  whitespace-split word windows (fast, language-agnostic)
  - tokens: tiktoken cl100k_base tokenization; falls back to words if tiktoken
            is not installed (no hard dependency on the optional package)
"""

from __future__ import annotations

from rag.chunking.protocols import Chunk
from rag.core.schemas import FixedChunkingConfig
from rag.observability.logging import get_logger

log = get_logger(__name__)


class FixedChunker:
    """Window-based chunker with optional token/char/word units."""

    def __init__(self, config: FixedChunkingConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # Chunker protocol
    # ------------------------------------------------------------------

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        if not text.strip():
            return []

        raw = self._split(text)
        return [
            Chunk(
                content=content,
                chunk_index=idx,
                metadata={"doc_id": doc_id, "unit": self._config.unit},
            )
            for idx, content in enumerate(raw)
            if content.strip()
        ]

    # ------------------------------------------------------------------
    # Internal splitting logic
    # ------------------------------------------------------------------

    def _split(self, text: str) -> list[str]:
        cfg = self._config
        size = cfg.chunk_size
        overlap = cfg.overlap
        step = max(1, size - overlap)

        if cfg.unit == "chars":
            units = list(text)
            sep = ""
        elif cfg.unit == "words":
            units = text.split()
            sep = " "
        else:  # tokens
            return self._split_tokens(text, size, overlap, step)

        if not units:
            return []

        return [
            sep.join(units[i : i + size])
            for i in range(0, len(units), step)
            if units[i : i + size]
        ]

    def _split_tokens(self, text: str, size: int, overlap: int, step: int) -> list[str]:
        try:
            import tiktoken  # noqa: PLC0415

            enc = tiktoken.get_encoding("cl100k_base")
            ids = enc.encode(text)
            if not ids:
                return []
            return [
                enc.decode(ids[i : i + size])
                for i in range(0, len(ids), step)
                if ids[i : i + size]
            ]
        except Exception:
            # tiktoken may fail to load BPE files in network-restricted environments.
            log.debug("chunking.fixed.tiktoken_unavailable", fallback="words")
            units = text.split()
            if not units:
                return []
            return [
                " ".join(units[i : i + size])
                for i in range(0, len(units), step)
                if units[i : i + size]
            ]
