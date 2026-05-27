"""
Tests for rag.chunking.strategies.sentence — SentenceChunker.

Verifies sentence grouping, min/max bounds, orphan-merge logic, and chunk
metadata fields.
"""

from __future__ import annotations

import pytest

from rag.chunking.protocols import Chunk, Chunker
from rag.chunking.strategies.sentence import SentenceChunker, _split_sentences
from rag.core.schemas import SentenceChunkingConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def _cfg(*, min_s: int = 2, max_s: int = 4) -> SentenceChunkingConfig:
    return SentenceChunkingConfig(min_sentences=min_s, max_sentences=max_s)


def _sents(n: int) -> str:
    """Build a string of n simple sentences."""
    return " ".join(f"Sentence {i}." for i in range(n))


# ── internal splitter ─────────────────────────────────────────────────────────


class TestSplitSentences:
    def test_splits_on_period(self):
        parts = _split_sentences("Hello. World.")
        assert parts == ["Hello.", "World."]

    def test_splits_on_exclamation(self):
        parts = _split_sentences("Hi! Bye!")
        assert parts == ["Hi!", "Bye!"]

    def test_splits_on_question_mark(self):
        parts = _split_sentences("How? Why?")
        assert parts == ["How?", "Why?"]

    def test_single_sentence_returns_one_item(self):
        parts = _split_sentences("Just one sentence.")
        assert parts == ["Just one sentence."]

    def test_no_trailing_empty_strings(self):
        parts = _split_sentences("One. Two. Three.")
        assert all(p for p in parts)


# ── empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string_returns_empty_list(self):
        chunker = SentenceChunker(_cfg())
        assert chunker.chunk("", doc_id="d") == []

    def test_whitespace_only_returns_empty_list(self):
        chunker = SentenceChunker(_cfg())
        assert chunker.chunk("   \n  ", doc_id="d") == []


# ── protocol ─────────────────────────────────────────────────────────────────


class TestProtocol:
    def test_satisfies_chunker_protocol(self):
        assert isinstance(SentenceChunker(_cfg()), Chunker)


# ── few-sentences edge cases ──────────────────────────────────────────────────


class TestFewSentences:
    def test_fewer_than_min_returns_single_chunk(self):
        chunker = SentenceChunker(_cfg(min_s=3, max_s=6))
        # 2 sentences < min=3
        result = chunker.chunk("Sent one. Sent two.", doc_id="d")
        assert len(result) == 1

    def test_exactly_min_returns_single_chunk(self):
        chunker = SentenceChunker(_cfg(min_s=2, max_s=4))
        result = chunker.chunk("One. Two.", doc_id="d")
        assert len(result) == 1

    def test_single_sentence_returns_one_chunk(self):
        chunker = SentenceChunker(_cfg())
        result = chunker.chunk("Just one.", doc_id="d")
        assert len(result) == 1


# ── windowing ─────────────────────────────────────────────────────────────────


class TestWindowing:
    def test_exact_multiple_gives_equal_windows(self):
        # 8 sentences, max=4 → exactly 2 chunks of 4
        chunker = SentenceChunker(_cfg(min_s=2, max_s=4))
        result = chunker.chunk(_sents(8), doc_id="d")
        assert len(result) == 2

    def test_no_sentences_lost(self):
        chunker = SentenceChunker(_cfg(min_s=2, max_s=3))
        text = _sents(9)
        result = chunker.chunk(text, doc_id="d")
        total = sum(len(_split_sentences(c.content)) for c in result)
        assert total == 9

    def test_chunk_does_not_exceed_max_sentences(self):
        chunker = SentenceChunker(_cfg(min_s=2, max_s=4))
        result = chunker.chunk(_sents(20), doc_id="d")
        for chunk in result:
            assert len(_split_sentences(chunk.content)) <= 4


# ── orphan merging ────────────────────────────────────────────────────────────


class TestOrphanMerging:
    def test_small_orphan_merged_into_previous(self):
        # 9 sentences, max=4 → windows [4], [4], [1] → last window (1) < min=2
        # → merged into second window giving [4], [5]
        chunker = SentenceChunker(_cfg(min_s=2, max_s=4))
        result = chunker.chunk(_sents(9), doc_id="d")
        assert len(result) == 2
        last_count = len(_split_sentences(result[-1].content))
        assert last_count >= 2  # after merge, last chunk is at least min_sentences

    def test_sufficient_orphan_not_merged(self):
        # 10 sentences, max=4 → [4], [4], [2] → last=2 == min=2, no merge
        chunker = SentenceChunker(_cfg(min_s=2, max_s=4))
        result = chunker.chunk(_sents(10), doc_id="d")
        assert len(result) == 3


# ── chunk fields ──────────────────────────────────────────────────────────────


class TestChunkFields:
    def test_chunk_index_is_sequential(self):
        chunker = SentenceChunker(_cfg())
        result = chunker.chunk(_sents(8), doc_id="d")
        assert [c.chunk_index for c in result] == list(range(len(result)))

    def test_metadata_contains_doc_id(self):
        chunker = SentenceChunker(_cfg())
        result = chunker.chunk("Hello. World.", doc_id="mydoc")
        assert result[0].metadata["doc_id"] == "mydoc"

    def test_parent_id_is_none(self):
        chunker = SentenceChunker(_cfg())
        result = chunker.chunk("Hello. World.", doc_id="d")
        assert result[0].parent_id is None

    def test_level_is_zero(self):
        chunker = SentenceChunker(_cfg())
        result = chunker.chunk("Hello. World.", doc_id="d")
        assert result[0].level == 0
