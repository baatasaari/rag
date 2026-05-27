"""
Tests for rag.chunking.strategies.fixed — FixedChunker.

Covers char / word / token units, windowing, overlap, and edge cases.
No external services are called; tiktoken absence is simulated via sys.modules.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from rag.chunking.protocols import Chunker
from rag.chunking.strategies.fixed import FixedChunker
from rag.core.schemas import FixedChunkingConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def _cfg(*, unit="words", size=5, overlap=1) -> FixedChunkingConfig:
    return FixedChunkingConfig(chunk_size=size, overlap=overlap, unit=unit)


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


# ── empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string_returns_empty_list(self):
        chunker = FixedChunker(_cfg())
        assert chunker.chunk("", doc_id="d") == []

    def test_whitespace_only_returns_empty_list(self):
        chunker = FixedChunker(_cfg())
        assert chunker.chunk("   \n\t  ", doc_id="d") == []


# ── Chunker protocol ──────────────────────────────────────────────────────────


class TestProtocol:
    def test_satisfies_chunker_protocol(self):
        chunker = FixedChunker(_cfg())
        assert isinstance(chunker, Chunker)


# ── word unit ─────────────────────────────────────────────────────────────────


class TestWordUnit:
    def test_short_text_is_one_chunk(self):
        chunker = FixedChunker(_cfg(size=10, overlap=0))
        result = chunker.chunk("hello world", doc_id="d")
        assert len(result) == 1
        assert result[0].content == "hello world"

    def test_splits_into_correct_number_of_chunks(self):
        # 10 words, size=5, overlap=1 → step=4 → chunks at 0,4,8 → 3 chunks
        chunker = FixedChunker(_cfg(size=5, overlap=1))
        result = chunker.chunk(_words(10), doc_id="d")
        assert len(result) == 3

    def test_each_chunk_has_correct_word_count(self):
        chunker = FixedChunker(_cfg(size=5, overlap=0))
        result = chunker.chunk(_words(10), doc_id="d")
        for chunk in result:
            assert len(chunk.content.split()) <= 5

    def test_last_chunk_contains_final_words(self):
        chunker = FixedChunker(_cfg(size=4, overlap=0))
        result = chunker.chunk("a b c d e f g", doc_id="d")
        # 7 words, size=4, step=4 → [a b c d], [e f g]
        last = result[-1].content.split()
        assert "g" in last

    def test_overlap_shares_words_between_chunks(self):
        # size=4, overlap=2, step=2
        chunker = FixedChunker(_cfg(size=4, overlap=2))
        words = "a b c d e f g h".split()
        result = chunker.chunk(" ".join(words), doc_id="d")
        # chunk[0] ends with words at idx 2,3; chunk[1] starts at idx 2
        chunk0_words = result[0].content.split()
        chunk1_words = result[1].content.split()
        assert chunk0_words[-2:] == chunk1_words[:2]

    def test_exact_boundary_is_one_chunk(self):
        chunker = FixedChunker(_cfg(size=5, overlap=0))
        result = chunker.chunk(_words(5), doc_id="d")
        assert len(result) == 1

    def test_chunk_index_is_sequential(self):
        chunker = FixedChunker(_cfg(size=3, overlap=0))
        result = chunker.chunk(_words(9), doc_id="d")
        assert [c.chunk_index for c in result] == list(range(len(result)))

    def test_metadata_contains_doc_id_and_unit(self):
        chunker = FixedChunker(_cfg(unit="words"))
        result = chunker.chunk("hello world", doc_id="mydoc")
        assert result[0].metadata["doc_id"] == "mydoc"
        assert result[0].metadata["unit"] == "words"

    def test_parent_id_is_none(self):
        chunker = FixedChunker(_cfg())
        result = chunker.chunk("hello world", doc_id="d")
        assert result[0].parent_id is None

    def test_level_is_zero(self):
        chunker = FixedChunker(_cfg())
        result = chunker.chunk("hello world", doc_id="d")
        assert result[0].level == 0

    def test_all_words_present_across_chunks_no_overlap(self):
        chunker = FixedChunker(_cfg(size=4, overlap=0))
        original_words = _words(13).split()
        result = chunker.chunk(" ".join(original_words), doc_id="d")
        # Every original word appears in some chunk.
        all_chunk_words = " ".join(c.content for c in result).split()
        assert set(original_words) == set(all_chunk_words)


# ── char unit ─────────────────────────────────────────────────────────────────


class TestCharUnit:
    def test_splits_by_character_count(self):
        chunker = FixedChunker(_cfg(unit="chars", size=5, overlap=0))
        result = chunker.chunk("abcdefghij", doc_id="d")
        assert len(result) == 2
        assert result[0].content == "abcde"
        assert result[1].content == "fghij"

    def test_overlap_repeats_chars(self):
        chunker = FixedChunker(_cfg(unit="chars", size=4, overlap=2))
        result = chunker.chunk("abcdef", doc_id="d")
        # step=2 → [abcd], [cdef]
        assert result[0].content[-2:] == result[1].content[:2]

    def test_metadata_unit_is_chars(self):
        chunker = FixedChunker(_cfg(unit="chars", size=10, overlap=0))
        result = chunker.chunk("hello", doc_id="d")
        assert result[0].metadata["unit"] == "chars"


# ── token unit ────────────────────────────────────────────────────────────────


class TestTokenUnit:
    def test_uses_tiktoken_when_available(self):
        """If tiktoken is importable, it should be used for tokenisation."""
        mock_enc = MagicMock()
        # Simulate 10 tokens for "hello world ..."
        mock_enc.encode.return_value = list(range(10))
        mock_enc.decode.side_effect = lambda ids: " ".join(str(i) for i in ids)

        mock_tiktoken = MagicMock()
        mock_tiktoken.get_encoding.return_value = mock_enc

        with patch.dict("sys.modules", {"tiktoken": mock_tiktoken}):
            chunker = FixedChunker(_cfg(unit="tokens", size=5, overlap=0))
            result = chunker.chunk("hello world foo bar baz qux quux", doc_id="d")

        mock_enc.encode.assert_called_once()
        assert len(result) == 2  # 10 tokens / 5 per chunk

    def test_fallback_to_words_when_tiktoken_absent(self):
        """Without tiktoken installed, unit=tokens falls back to word splitting."""
        with patch.dict("sys.modules", {"tiktoken": None}):
            chunker = FixedChunker(_cfg(unit="tokens", size=3, overlap=0))
            result = chunker.chunk("a b c d e f", doc_id="d")
        # 6 words, size=3, overlap=0 → 2 chunks
        assert len(result) == 2

    def test_fallback_result_is_words_not_chars(self):
        with patch.dict("sys.modules", {"tiktoken": None}):
            chunker = FixedChunker(_cfg(unit="tokens", size=2, overlap=0))
            result = chunker.chunk("hello world foo", doc_id="d")
        assert result[0].content == "hello world"
        assert result[1].content == "foo"
