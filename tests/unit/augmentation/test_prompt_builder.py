"""
Tests for rag.augmentation.prompt_builder — PromptBuilder.
"""

from __future__ import annotations

import pytest

from rag.core.schemas import CitationMode
from rag.augmentation.citations import CitationBuilder
from rag.augmentation.prompt_builder import AssembledPrompt, PromptBuilder
from rag.augmentation.protocols import AugmentedContext, Citation
from rag.retrieval.protocols import RetrievalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _result(chunk_id: str = "c1", content: str = "chunk content") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        doc_id="doc1",
        content=content,
        score=0.9,
        rank=0,
        retrieval_method="dense",
        metadata={"title": f"Doc {chunk_id}", "source_uri": f"gs://bucket/{chunk_id}.pdf"},
    )


def _citation(index: int, title: str = "Doc", mode: CitationMode = CitationMode.INLINE) -> Citation:
    return Citation(
        index=index,
        chunk_id=f"c{index}",
        doc_id=f"doc{index}",
        source_uri=f"gs://bucket/doc{index}.pdf",
        title=title,
        page=None,
        mode=mode,
        snippet="short snippet",
    )


def _ctx(
    query: str = "What is the policy?",
    n_chunks: int = 2,
    mode: CitationMode = CitationMode.INLINE,
) -> AugmentedContext:
    results = [_result(f"c{i}", f"Content of chunk {i}. " * 5) for i in range(n_chunks)]
    compressed = [f"Compressed chunk {i}." for i in range(n_chunks)]
    citations = [_citation(i + 1, f"Doc {i}", mode) for i in range(n_chunks)]
    return AugmentedContext(
        query=query,
        results=results,
        compressed_chunks=compressed,
        citations=citations,
        total_chars=sum(len(c) for c in compressed),
    )


# ── AssembledPrompt dataclass ─────────────────────────────────────────────────

class TestAssembledPrompt:
    def test_is_dataclass(self):
        p = AssembledPrompt(
            system="sys", context_block="ctx", sources_block="src",
            user_message="q", total_chars=100, chunks_included=2, chunks_dropped=0
        )
        assert p.chunks_included == 2
        assert p.chunks_dropped == 0


# ── PromptBuilder.build ───────────────────────────────────────────────────────

class TestPromptBuilderBuild:
    def test_returns_assembled_prompt(self):
        builder = PromptBuilder()
        result = builder.build(_ctx())
        assert isinstance(result, AssembledPrompt)

    def test_context_block_contains_chunks(self):
        builder = PromptBuilder()
        ctx = _ctx(n_chunks=2)
        result = builder.build(ctx)
        assert "Compressed chunk 0" in result.context_block
        assert "Compressed chunk 1" in result.context_block

    def test_context_block_has_delimiters(self):
        builder = PromptBuilder()
        result = builder.build(_ctx())
        assert "--- CONTEXT ---" in result.context_block
        assert "--- END CONTEXT ---" in result.context_block

    def test_sources_block_has_delimiters(self):
        builder = PromptBuilder()
        result = builder.build(_ctx())
        assert "--- SOURCES ---" in result.sources_block
        assert "--- END SOURCES ---" in result.sources_block

    def test_user_message_contains_query(self):
        builder = PromptBuilder()
        ctx = _ctx(query="What is the capital requirement?")
        result = builder.build(ctx)
        assert "What is the capital requirement?" in result.user_message

    def test_user_message_has_answer_prompt(self):
        builder = PromptBuilder()
        result = builder.build(_ctx())
        assert "Answer:" in result.user_message

    def test_system_lbg_default(self):
        builder = PromptBuilder(system_template="lbg-default")
        result = builder.build(_ctx())
        assert "Lloyds Banking Group" in result.system

    def test_custom_system_prompt(self):
        builder = PromptBuilder(system_template="You are a helpful assistant.")
        result = builder.build(_ctx())
        assert result.system == "You are a helpful assistant."

    def test_chunks_included_count(self):
        builder = PromptBuilder()
        result = builder.build(_ctx(n_chunks=3))
        assert result.chunks_included == 3
        assert result.chunks_dropped == 0

    def test_inline_citation_marker_in_context(self):
        builder = PromptBuilder()
        ctx = _ctx(n_chunks=2, mode=CitationMode.INLINE)
        result = builder.build(ctx)
        assert "[1]" in result.context_block

    def test_no_citations_when_none_mode(self):
        builder = PromptBuilder()
        ctx = _ctx(n_chunks=2, mode=CitationMode.NONE)
        result = builder.build(ctx)
        # NONE mode: format_inline_marker returns "", format_footnote_list returns ""
        assert result.sources_block == ""

    def test_total_chars_is_sum_of_parts(self):
        builder = PromptBuilder()
        result = builder.build(_ctx())
        expected = (
            len(result.system)
            + len(result.context_block)
            + len(result.sources_block)
            + len(result.user_message)
        )
        assert result.total_chars == expected


# ── Context window truncation ─────────────────────────────────────────────────

class TestContextWindowTruncation:
    def test_excess_chunks_dropped(self):
        # Set tiny max_chars so only a few chunks fit
        builder = PromptBuilder(max_chars=600)
        ctx = _ctx(n_chunks=10)
        result = builder.build(ctx)
        assert result.chunks_dropped > 0
        assert result.chunks_included + result.chunks_dropped == 10

    def test_first_chunk_always_included(self):
        builder = PromptBuilder(max_chars=500)
        ctx = _ctx(n_chunks=5)
        result = builder.build(ctx)
        assert result.chunks_included >= 1
        assert "Compressed chunk 0" in result.context_block

    def test_no_truncation_needed_when_fits(self):
        builder = PromptBuilder(max_chars=_DEFAULT_MAX_CHARS())
        ctx = _ctx(n_chunks=2)
        result = builder.build(ctx)
        assert result.chunks_dropped == 0

    def test_empty_context_produces_empty_context_block(self):
        builder = PromptBuilder()
        ctx = AugmentedContext(
            query="q",
            results=[],
            compressed_chunks=[],
            citations=[],
            total_chars=0,
        )
        result = builder.build(ctx)
        assert result.context_block == ""
        assert result.sources_block == ""
        assert result.chunks_included == 0
        assert result.chunks_dropped == 0


def _DEFAULT_MAX_CHARS() -> int:
    from rag.augmentation.prompt_builder import _DEFAULT_MAX_CHARS
    return _DEFAULT_MAX_CHARS


# ── full_prompt convenience method ────────────────────────────────────────────

class TestFullPrompt:
    def test_contains_all_sections(self):
        builder = PromptBuilder()
        ctx = _ctx(n_chunks=2)
        prompt = builder.full_prompt(ctx)
        assert "Lloyds Banking Group" in prompt
        assert "--- CONTEXT ---" in prompt
        assert "--- SOURCES ---" in prompt
        assert "Question:" in prompt
        assert "Answer:" in prompt

    def test_returns_string(self):
        builder = PromptBuilder()
        result = builder.full_prompt(_ctx())
        assert isinstance(result, str)

    def test_sections_separated_by_double_newline(self):
        builder = PromptBuilder()
        prompt = builder.full_prompt(_ctx())
        assert "\n\n" in prompt

    def test_empty_context_omits_context_and_sources_sections(self):
        builder = PromptBuilder()
        ctx = AugmentedContext(
            query="bare query", results=[], compressed_chunks=[], citations=[], total_chars=0
        )
        prompt = builder.full_prompt(ctx)
        assert "--- CONTEXT ---" not in prompt
        assert "--- SOURCES ---" not in prompt
        assert "bare query" in prompt
