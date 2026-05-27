"""
LBG RAG — Query Orchestrator (Pipeline Layer)

Public surface:
  QueryContext   — per-request user context (query, roles, filters, options)
  RAGResult      — complete pipeline output (answer + retrieval + metrics)
  RAGPipeline    — top-level orchestrator: embed → retrieve → augment → generate
"""

from rag.pipeline.context import QueryContext
from rag.pipeline.result import RAGResult
from rag.pipeline.orchestrator import RAGPipeline

__all__ = [
    "QueryContext",
    "RAGResult",
    "RAGPipeline",
]
