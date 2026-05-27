"""
Tests for rag.retrieval.mmr — apply_mmr and _jaccard.
"""

from __future__ import annotations

import pytest

from rag.retrieval.mmr import apply_mmr, _jaccard
from rag.retrieval.protocols import RetrievalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(chunk_id: str, score: float, content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=content,
        score=score,
        rank=0,
        retrieval_method="dense",
        metadata={},
    )


# ── _jaccard ──────────────────────────────────────────────────────────────────

class TestJaccard:
    def test_identical_strings_return_one(self):
        assert _jaccard("hello world", "hello world") == 1.0

    def test_disjoint_strings_return_zero(self):
        assert _jaccard("apple orange", "banana grape") == 0.0

    def test_partial_overlap(self):
        # {"a","b"} ∩ {"b","c"} = {"b"}, ∪ = {"a","b","c"}
        assert abs(_jaccard("a b", "b c") - 1 / 3) < 1e-9

    def test_empty_strings_return_zero(self):
        assert _jaccard("", "") == 0.0

    def test_empty_vs_nonempty_return_zero(self):
        assert _jaccard("", "hello") == 0.0

    def test_case_insensitive(self):
        assert _jaccard("Hello World", "hello world") == 1.0


# ── apply_mmr ─────────────────────────────────────────────────────────────────

class TestApplyMMR:
    def test_empty_candidates_returns_empty(self):
        assert apply_mmr([], top_n=5, lambda_param=0.5) == []

    def test_top_n_limits_output(self):
        candidates = [
            _result("c1", 0.9, "the quick brown fox jumps over the lazy dog"),
            _result("c2", 0.8, "python machine learning neural network"),
            _result("c3", 0.7, "regulatory compliance banking finance"),
            _result("c4", 0.6, "cloud infrastructure gcp kubernetes"),
        ]
        results = apply_mmr(candidates, top_n=2, lambda_param=0.5)
        assert len(results) == 2

    def test_top_n_greater_than_candidates(self):
        candidates = [_result("c1", 0.9, "hello world")]
        results = apply_mmr(candidates, top_n=10, lambda_param=0.5)
        assert len(results) == 1

    def test_lambda_one_preserves_relevance_order(self):
        candidates = [
            _result("c1", 0.9, "identical content word for word exactly"),
            _result("c2", 0.8, "identical content word for word exactly"),
        ]
        results = apply_mmr(candidates, top_n=2, lambda_param=1.0)
        assert results[0].chunk_id == "c1"

    def test_lambda_zero_selects_diverse_result_second(self):
        candidates = [
            _result("c1", 0.9, "banking finance regulatory compliance rules"),
            _result("c2", 0.85, "banking finance regulatory compliance rules"),  # very similar
            _result("c3", 0.7, "python deep learning neural network tensorflow"),  # very different
        ]
        results = apply_mmr(candidates, top_n=2, lambda_param=0.0)
        # First pick is always highest score (c1), second should be most diverse (c3)
        assert results[0].chunk_id == "c1"
        assert results[1].chunk_id == "c3"

    def test_output_ranks_are_zero_based_sequential(self):
        candidates = [
            _result(f"c{i}", 1.0 - i * 0.1, f"content {i} with unique words cluster {i}")
            for i in range(4)
        ]
        results = apply_mmr(candidates, top_n=3, lambda_param=0.5)
        assert [r.rank for r in results] == [0, 1, 2]

    def test_retrieval_method_preserved(self):
        candidates = [_result("c1", 0.9, "test content about banking")]
        results = apply_mmr(candidates, top_n=1, lambda_param=0.5)
        assert results[0].retrieval_method == "dense"

    def test_single_candidate_returned_unchanged(self):
        candidates = [_result("c1", 0.9, "the only result")]
        results = apply_mmr(candidates, top_n=1, lambda_param=0.5)
        assert results[0].chunk_id == "c1"
        assert results[0].score == 0.9
