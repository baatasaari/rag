"""
Tests for rag.augmentation.citations — CitationBuilder.
"""

from __future__ import annotations

import pytest

from rag.core.schemas import CitationMode
from rag.augmentation.citations import CitationBuilder, _snippet
from rag.augmentation.protocols import Citation
from rag.retrieval.protocols import RetrievalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(
    chunk_id: str = "c1",
    doc_id: str = "doc1",
    content: str = "sample content for testing",
    metadata: dict | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_id=doc_id,
        content=content,
        score=0.9,
        rank=0,
        retrieval_method="dense",
        metadata=metadata or {},
    )


# ── _snippet ──────────────────────────────────────────────────────────────────

class TestSnippet:
    def test_short_text_returned_unchanged(self):
        text = "short text"
        assert _snippet(text) == text

    def test_long_text_truncated_at_word_boundary(self):
        text = "word " * 30  # 150 chars
        result = _snippet(text)
        assert len(result) <= 125  # 120 + " …"
        assert result.endswith("…")

    def test_ellipsis_appended(self):
        text = "a" * 130
        result = _snippet(text)
        assert "…" in result

    def test_leading_whitespace_stripped(self):
        text = "   hello world"
        assert _snippet(text) == "hello world"


# ── CitationBuilder.build ─────────────────────────────────────────────────────

class TestCitationBuilderBuild:
    def test_returns_one_citation_per_result(self):
        builder = CitationBuilder(CitationMode.INLINE)
        results = [_result(f"c{i}", f"doc{i}") for i in range(3)]
        citations = builder.build(results)
        assert len(citations) == 3

    def test_citation_indices_are_one_based(self):
        builder = CitationBuilder(CitationMode.INLINE)
        results = [_result(f"c{i}") for i in range(3)]
        citations = builder.build(results)
        assert [c.index for c in citations] == [1, 2, 3]

    def test_empty_results_returns_empty(self):
        builder = CitationBuilder(CitationMode.INLINE)
        assert builder.build([]) == []

    def test_mode_propagated_to_citations(self):
        builder = CitationBuilder(CitationMode.FOOTNOTE)
        citations = builder.build([_result()])
        assert citations[0].mode == CitationMode.FOOTNOTE

    def test_source_uri_from_metadata(self):
        meta = {"source_uri": "gs://lbg-docs/policy.pdf"}
        citations = CitationBuilder(CitationMode.INLINE).build([_result(metadata=meta)])
        assert citations[0].source_uri == "gs://lbg-docs/policy.pdf"

    def test_source_uri_falls_back_to_source_key(self):
        meta = {"source": "some/path.txt"}
        citations = CitationBuilder(CitationMode.INLINE).build([_result(metadata=meta)])
        assert citations[0].source_uri == "some/path.txt"

    def test_title_from_metadata(self):
        meta = {"title": "Capital Requirements Policy"}
        citations = CitationBuilder(CitationMode.INLINE).build([_result(metadata=meta)])
        assert citations[0].title == "Capital Requirements Policy"

    def test_title_falls_back_to_doc_id(self):
        citations = CitationBuilder(CitationMode.INLINE).build([_result(doc_id="docABC")])
        assert citations[0].title == "docABC"

    def test_page_from_metadata(self):
        meta = {"page": 42}
        citations = CitationBuilder(CitationMode.INLINE).build([_result(metadata=meta)])
        assert citations[0].page == 42

    def test_page_none_when_absent(self):
        citations = CitationBuilder(CitationMode.INLINE).build([_result()])
        assert citations[0].page is None

    def test_snippet_populated_from_content(self):
        result = _result(content="The quick brown fox jumps over the lazy dog.")
        citations = CitationBuilder(CitationMode.INLINE).build([result])
        assert "quick brown fox" in citations[0].snippet


# ── format_inline_marker ──────────────────────────────────────────────────────

class TestFormatInlineMarker:
    def test_inline_mode_returns_bracket(self):
        c = Citation(1, "c1", "d1", "", "title", None, CitationMode.INLINE, "snippet")
        assert CitationBuilder.format_inline_marker(c) == "[1]"

    def test_footnote_mode_returns_empty(self):
        c = Citation(2, "c1", "d1", "", "title", None, CitationMode.FOOTNOTE, "snippet")
        assert CitationBuilder.format_inline_marker(c) == ""

    def test_none_mode_returns_empty(self):
        c = Citation(3, "c1", "d1", "", "title", None, CitationMode.NONE, "snippet")
        assert CitationBuilder.format_inline_marker(c) == ""


# ── format_footnote_list ──────────────────────────────────────────────────────

class TestFormatFootnoteList:
    def test_empty_list_returns_empty(self):
        assert CitationBuilder.format_footnote_list([]) == ""

    def test_none_mode_returns_empty(self):
        c = Citation(1, "c1", "d1", "", "title", None, CitationMode.NONE, "snippet")
        assert CitationBuilder.format_footnote_list([c]) == ""

    def test_inline_mode_produces_footnote_list(self):
        c = Citation(1, "c1", "d1", "gs://bucket/file.pdf", "My Doc", 5, CitationMode.INLINE, "snippet")
        result = CitationBuilder.format_footnote_list([c])
        assert "[1]" in result
        assert "My Doc" in result
        assert "gs://bucket/file.pdf" in result
        assert "p.5" in result

    def test_multiple_citations_ordered(self):
        citations = [
            Citation(i, f"c{i}", f"d{i}", "", f"Doc {i}", None, CitationMode.FOOTNOTE, "snippet")
            for i in range(1, 4)
        ]
        result = CitationBuilder.format_footnote_list(citations)
        lines = result.strip().splitlines()
        assert len(lines) == 3
        assert lines[0].startswith("[1]")
        assert lines[2].startswith("[3]")

    def test_missing_source_uri_omitted(self):
        c = Citation(1, "c1", "d1", "", "Title", None, CitationMode.INLINE, "snippet")
        result = CitationBuilder.format_footnote_list([c])
        assert "<" not in result  # no URI angle brackets

    def test_missing_page_omitted(self):
        c = Citation(1, "c1", "d1", "gs://x", "Title", None, CitationMode.INLINE, "snippet")
        result = CitationBuilder.format_footnote_list([c])
        assert "p." not in result
