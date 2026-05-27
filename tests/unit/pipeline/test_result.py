"""
Tests for rag.pipeline.result — RAGResult.
"""

from __future__ import annotations

from rag.core.schemas import CitationMode
from rag.augmentation.protocols import Citation
from rag.pipeline.result import RAGResult
from rag.retrieval.protocols import RetrievalResult


def _citation(idx: int) -> Citation:
    return Citation(
        index=idx, chunk_id=f"c{idx}", doc_id=f"d{idx}",
        source_uri="gs://bucket/doc.pdf", title=f"Doc {idx}",
        page=None, mode=CitationMode.INLINE, snippet="snippet",
    )


def _result(chunk_id: str = "c1") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id, doc_id="doc1", content="content",
        score=0.9, rank=0, retrieval_method="dense", metadata={},
    )


def _rag_result(**overrides) -> RAGResult:
    defaults = dict(
        query_id="qid1",
        query="What is the policy?",
        answer="The policy requires [1] compliance.",
        citations=[_citation(1)],
        retrieval_results=[_result()],
        chunks_retrieved=5,
        chunks_used=3,
        tokens_in=100,
        tokens_out=40,
        cached=False,
        provider="vertex_ai",
        model="gemini-2.0-flash",
        latency_ms=320.5,
        citations_used=[1],
    )
    defaults.update(overrides)
    return RAGResult(**defaults)


class TestRAGResult:
    def test_total_tokens_property(self):
        r = _rag_result(tokens_in=100, tokens_out=40)
        assert r.total_tokens == 140

    def test_total_tokens_zero_on_cache_hit(self):
        r = _rag_result(tokens_in=0, tokens_out=0, cached=True)
        assert r.total_tokens == 0

    def test_metadata_defaults_empty(self):
        r = _rag_result()
        assert r.metadata == {}

    def test_cached_flag(self):
        r = _rag_result(cached=True)
        assert r.cached is True

    def test_citations_list_preserved(self):
        r = _rag_result(citations=[_citation(1), _citation(2)])
        assert len(r.citations) == 2

    def test_retrieval_results_preserved(self):
        results = [_result(f"c{i}") for i in range(3)]
        r = _rag_result(retrieval_results=results)
        assert len(r.retrieval_results) == 3

    def test_chunks_retrieved_and_used(self):
        r = _rag_result(chunks_retrieved=10, chunks_used=5)
        assert r.chunks_retrieved == 10
        assert r.chunks_used == 5

    def test_latency_ms_float(self):
        r = _rag_result(latency_ms=123.456)
        assert isinstance(r.latency_ms, float)

    def test_citations_used_list(self):
        r = _rag_result(citations_used=[1, 3])
        assert r.citations_used == [1, 3]

    def test_empty_answer(self):
        r = _rag_result(answer="")
        assert r.answer == ""
