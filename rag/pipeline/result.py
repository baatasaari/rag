"""
RAGResult — complete pipeline output returned by RAGPipeline.query().

All fields are populated before the result is returned.  For streaming
calls the answer is the full concatenated response after the stream ends.

Token counts follow the provider's native usage reporting.  For cache hits
tokens_in and tokens_out are both 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag.augmentation.protocols import Citation
from rag.retrieval.protocols import RetrievalResult


@dataclass
class RAGResult:
    """Complete output of a single RAG pipeline invocation."""

    query_id: str
    query: str
    answer: str

    # Source attribution
    citations: list[Citation]

    # Retrieval diagnostics
    retrieval_results: list[RetrievalResult]
    chunks_retrieved: int        # candidates before reranking/MMR
    chunks_used: int             # chunks in the final prompt

    # Generation diagnostics
    tokens_in: int
    tokens_out: int
    cached: bool
    provider: str
    model: str
    latency_ms: float

    # Citations from the answer text ([N] indices)
    citations_used: list[int]

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out
