"""
Tests for rag.chunking.strategies.recursive — RecursiveChunker.

All sizes are in characters.  Verifies separator priority, recursive
splitting, overlap merging, and hard-split fallback.
"""

from __future__ import annotations

import pytest

from rag.chunking.protocols import Chunker
from rag.chunking.strategies.recursive import RecursiveChunker
from rag.core.schemas import RecursiveChunkingConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def _cfg(*, size=20, overlap=0, seps=None) -> RecursiveChunkingConfig:
    kwargs: dict = {"chunk_size": size, "overlap": overlap}
    if seps is not None:
        kwargs["separators"] = seps
    return RecursiveChunkingConfig(**kwargs)


# ── empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string_returns_empty(self):
        chunker = RecursiveChunker(_cfg())
        assert chunker.chunk("", doc_id="d") == []

    def test_whitespace_only_returns_empty(self):
        chunker = RecursiveChunker(_cfg())
        assert chunker.chunk("  \n  ", doc_id="d") == []


# ── protocol ──────────────────────────────────────────────────────────────────


class TestProtocol:
    def test_satisfies_chunker_protocol(self):
        assert isinstance(RecursiveChunker(_cfg()), Chunker)


# ── short text ────────────────────────────────────────────────────────────────


class TestShortText:
    def test_text_within_chunk_size_is_one_chunk(self):
        chunker = RecursiveChunker(_cfg(size=100))
        result = chunker.chunk("short text", doc_id="d")
        assert len(result) == 1
        assert result[0].content == "short text"

    def test_text_exactly_chunk_size_is_one_chunk(self):
        text = "x" * 20
        chunker = RecursiveChunker(_cfg(size=20))
        result = chunker.chunk(text, doc_id="d")
        assert len(result) == 1


# ── separator splitting ───────────────────────────────────────────────────────


class TestSeparatorSplitting:
    def test_splits_on_double_newline_first(self):
        # Two paragraphs, each within chunk_size
        text = "paragraph one here.\n\nparagraph two here."
        chunker = RecursiveChunker(_cfg(size=30, overlap=0, seps=["\n\n", "\n", " "]))
        result = chunker.chunk(text, doc_id="d")
        assert len(result) == 2

    def test_falls_back_to_single_newline(self):
        # Only \n present, not \n\n
        lines = "\n".join(["short line"] * 4)
        chunker = RecursiveChunker(_cfg(size=15, overlap=0, seps=["\n\n", "\n", " "]))
        result = chunker.chunk(lines, doc_id="d")
        assert len(result) >= 2

    def test_falls_back_to_space_when_no_newlines(self):
        text = "word " * 20  # 100 chars (5 per word + space)
        chunker = RecursiveChunker(_cfg(size=15, overlap=0, seps=["\n\n", "\n", " "]))
        result = chunker.chunk(text.strip(), doc_id="d")
        assert len(result) > 1

    def test_chunk_index_is_sequential(self):
        text = "a b c d e f g h i j k l m n o p"
        chunker = RecursiveChunker(_cfg(size=6, overlap=0, seps=[" "]))
        result = chunker.chunk(text, doc_id="d")
        assert [c.chunk_index for c in result] == list(range(len(result)))

    def test_all_content_preserved(self):
        # All characters in the original appear somewhere in the output
        text = "Hello world.\n\nGoodbye cruel world.\n\nThe end."
        chunker = RecursiveChunker(_cfg(size=25, overlap=0))
        result = chunker.chunk(text, doc_id="d")
        combined = " ".join(c.content for c in result)
        for word in ["Hello", "Goodbye", "end"]:
            assert word in combined


# ── overlap ───────────────────────────────────────────────────────────────────


class TestOverlap:
    def test_overlap_repeats_content_between_chunks(self):
        # size=10, overlap=3 → step=7
        text = "abcdefghijklmnopqrstuvwxyz"
        chunker = RecursiveChunker(_cfg(size=10, overlap=3, seps=[]))
        result = chunker.chunk(text, doc_id="d")
        if len(result) >= 2:
            tail = result[0].content[-3:]
            assert tail in result[1].content


# ── hard split ────────────────────────────────────────────────────────────────


class TestHardSplit:
    def test_no_separator_found_hard_splits_by_chars(self):
        # No separator in text and separators list is empty → hard char split
        text = "a" * 50
        chunker = RecursiveChunker(_cfg(size=10, overlap=0, seps=[]))
        result = chunker.chunk(text, doc_id="d")
        assert len(result) == 5
        for chunk in result:
            assert len(chunk.content) == 10


# ── metadata / fields ─────────────────────────────────────────────────────────


class TestChunkFields:
    def test_metadata_contains_doc_id(self):
        chunker = RecursiveChunker(_cfg(size=100))
        result = chunker.chunk("hello world", doc_id="docA")
        assert result[0].metadata["doc_id"] == "docA"

    def test_parent_id_is_none(self):
        chunker = RecursiveChunker(_cfg(size=100))
        result = chunker.chunk("hello world", doc_id="d")
        assert result[0].parent_id is None

    def test_level_is_zero(self):
        chunker = RecursiveChunker(_cfg(size=100))
        result = chunker.chunk("hello world", doc_id="d")
        assert result[0].level == 0
