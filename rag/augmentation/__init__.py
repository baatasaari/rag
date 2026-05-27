"""
LBG RAG — Augmentation Layer

Public surface:
  Citation         — a source reference (INLINE / FOOTNOTE / NONE mode)
  AugmentedContext — compressed chunks + citations ready for prompt assembly
  Compressor       — Protocol satisfied by context compressors
  ContextCompressor — multi-strategy compressor (LLM_EXTRACT / SENTENCE_WINDOW / MAP_REDUCE)
  CitationBuilder  — extracts and formats citations from retrieval results
  PromptBuilder    — assembles the final LLM prompt with context + citations
"""

from rag.augmentation.protocols import AugmentedContext, Citation, Compressor
from rag.augmentation.compressor import ContextCompressor
from rag.augmentation.citations import CitationBuilder
from rag.augmentation.prompt_builder import PromptBuilder

__all__ = [
    "AugmentedContext",
    "Citation",
    "Compressor",
    "ContextCompressor",
    "CitationBuilder",
    "PromptBuilder",
]
