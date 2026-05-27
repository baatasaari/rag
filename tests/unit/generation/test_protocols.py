"""
Tests for rag.generation.protocols — GeneratedAnswer and _extract_citation_indices.
"""

from __future__ import annotations

import pytest

from rag.generation.protocols import GeneratedAnswer, _extract_citation_indices


# ── _extract_citation_indices ─────────────────────────────────────────────────

class TestExtractCitationIndices:
    def test_extracts_single_index(self):
        assert _extract_citation_indices("See [1] for details.") == [1]

    def test_extracts_multiple_indices(self):
        result = _extract_citation_indices("Sources [1] and [3] confirm this [2].")
        assert result == [1, 2, 3]  # sorted

    def test_deduplicates_indices(self):
        assert _extract_citation_indices("[1] foo [1] bar") == [1]

    def test_no_citations_returns_empty(self):
        assert _extract_citation_indices("No references here.") == []

    def test_empty_string_returns_empty(self):
        assert _extract_citation_indices("") == []

    def test_returns_sorted(self):
        indices = _extract_citation_indices("[3] first [1] second [2] third")
        assert indices == [1, 2, 3]


# ── GeneratedAnswer ───────────────────────────────────────────────────────────

class TestGeneratedAnswer:
    def test_citations_auto_extracted_on_init(self):
        ans = GeneratedAnswer(
            answer="The policy [1] states that [3] applies.",
            tokens_in=100,
            tokens_out=50,
            model="gemini-2.0-flash",
            provider="vertex_ai",
        )
        assert ans.citations_used == [1, 3]

    def test_explicit_citations_not_overwritten_if_set(self):
        ans = GeneratedAnswer(
            answer="No markers in text",
            tokens_in=10,
            tokens_out=5,
            model="gemini",
            provider="vertex_ai",
            citations_used=[],
        )
        # __post_init__ only fills in citations_used when it's empty
        assert ans.citations_used == []

    def test_defaults(self):
        ans = GeneratedAnswer(
            answer="hello",
            tokens_in=1,
            tokens_out=1,
            model="m",
            provider="p",
        )
        assert ans.cached is False
        assert ans.latency_ms == 0.0
        assert ans.metadata == {}

    def test_cached_flag_preserved(self):
        ans = GeneratedAnswer(
            answer="cached response",
            tokens_in=0,
            tokens_out=0,
            model="m",
            provider="p",
            cached=True,
        )
        assert ans.cached is True
