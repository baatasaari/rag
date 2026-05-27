"""
LBG RAG — Retrieval Layer

Public surface:
  RetrievalResult  — canonical result type flowing through all retrievers
  Retriever        — structural Protocol every retriever must satisfy
  DenseRetriever   — pgvector cosine similarity (AlloyDB)
  SparseRetriever  — BM25 / FTS / Vertex AI Search
  HybridRetriever  — RRF / LINEAR fusion of dense + sparse
  Reranker         — Cohere / cross-encoder with automatic fallback
  apply_mmr        — Maximal Marginal Relevance diversity re-ranking
  RetrievalEngine  — orchestrator (query-transform → retrieve → rerank)
"""

from rag.retrieval.protocols import RetrievalResult, Retriever
from rag.retrieval.dense import DenseRetriever
from rag.retrieval.sparse import SparseRetriever
from rag.retrieval.fusion import HybridRetriever
from rag.retrieval.reranker import Reranker
from rag.retrieval.mmr import apply_mmr
from rag.retrieval.engine import RetrievalEngine

__all__ = [
    "RetrievalResult",
    "Retriever",
    "DenseRetriever",
    "SparseRetriever",
    "HybridRetriever",
    "Reranker",
    "apply_mmr",
    "RetrievalEngine",
]
