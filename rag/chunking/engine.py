"""
ChunkingEngine — strategy selector and OTel-instrumented orchestrator.

Reads ``ChunkingConfig.strategy`` to instantiate the correct :class:`Chunker`
implementation, then wraps the ``chunk()`` call in an OTel span that records
the strategy, document ID, and resulting chunk count.

Supported strategies (Module 6):
  - fixed       → FixedChunker
  - sentence    → SentenceChunker
  - recursive   → RecursiveChunker
  - hierarchical → HierarchicalChunker
  - semantic    → SemanticChunker

AGENTIC / AST / RAPTOR / LATE_CHUNKING are schema-valid but not yet
implemented at runtime; they raise ``NotImplementedError``.
"""

from __future__ import annotations

from typing import Callable

from rag.chunking.protocols import Chunk, Chunker
from rag.chunking.strategies.fixed import FixedChunker
from rag.chunking.strategies.hierarchical import HierarchicalChunker
from rag.chunking.strategies.recursive import RecursiveChunker
from rag.chunking.strategies.semantic import SemanticChunker
from rag.chunking.strategies.sentence import SentenceChunker
from rag.core.schemas import ChunkingConfig, ChunkingStrategy
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)


class ChunkingEngine:
    """Strategy-agnostic chunking orchestrator.

    Args:
        config:    ChunkingConfig from RAGConfig.chunking.
        embed_fn:  Optional embedding callable used by SemanticChunker.
                   Signature: ``(list[str]) -> list[list[float]]``.
                   Ignored for non-semantic strategies.
    """

    def __init__(
        self,
        config: ChunkingConfig,
        *,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
    ) -> None:
        self._config = config
        self._chunker: Chunker = self._build_chunker(embed_fn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, text: str, *, doc_id: str) -> list[Chunk]:
        """Chunk *text* using the configured strategy.

        Args:
            text:   Raw document text.
            doc_id: Stable document identifier propagated to each chunk's
                    metadata and used for hierarchical parent-id construction.

        Returns:
            Ordered list of :class:`~rag.chunking.protocols.Chunk` objects.
        """
        with record_span(
            "chunking",
            **{
                RAGAttributes.SOURCE_URI: doc_id,
                "rag.chunking.strategy": self._config.strategy.value,
            },
        ) as span:
            result = self._chunker.chunk(text, doc_id=doc_id)
            span.set_attribute(RAGAttributes.CHUNK_COUNT, len(result))
            log.info(
                "chunking.complete",
                doc_id=doc_id,
                strategy=self._config.strategy.value,
                chunk_count=len(result),
            )
            return result

    # ------------------------------------------------------------------
    # Strategy construction
    # ------------------------------------------------------------------

    def _build_chunker(
        self,
        embed_fn: Callable[[list[str]], list[list[float]]] | None,
    ) -> Chunker:
        strategy = self._config.strategy

        if strategy == ChunkingStrategy.FIXED:
            return FixedChunker(self._config.fixed)

        if strategy == ChunkingStrategy.SENTENCE:
            return SentenceChunker(self._config.sentence)

        if strategy == ChunkingStrategy.RECURSIVE:
            return RecursiveChunker(self._config.recursive)

        if strategy == ChunkingStrategy.HIERARCHICAL:
            return HierarchicalChunker(self._config.hierarchical)

        if strategy == ChunkingStrategy.SEMANTIC:
            return SemanticChunker(self._config.semantic, embed_fn=embed_fn)

        raise NotImplementedError(
            f"Chunking strategy '{strategy.value}' is defined in the schema "
            "but not yet implemented in ChunkingEngine.  "
            "Implement a dedicated Chunker class and register it here."
        )
