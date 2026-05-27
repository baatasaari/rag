"""
Tests for rag.chunking.strategies.semantic — SemanticChunker.

No external services are used.  Tests inject deterministic embed_fn callables
that return controlled similarity patterns, allowing reliable breakpoint
detection verification.
"""

from __future__ import annotations

import math

import pytest

from rag.chunking.protocols import Chunker
from rag.chunking.strategies.semantic import (
    SemanticChunker,
    _bag_of_chars,
    _cosine,
    _split_sentences,
)
from rag.core.schemas import SemanticChunkingConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def _cfg(
    *,
    breakpoint_type="percentile",
    threshold=95.0,
    buffer=0,
) -> SemanticChunkingConfig:
    return SemanticChunkingConfig(
        breakpoint_type=breakpoint_type,
        breakpoint_threshold=threshold,
        buffer_size=buffer,
    )


def _orthogonal_embed(texts: list[str]) -> list[list[float]]:
    """Return orthogonal unit vectors — max distance between every pair."""
    result = []
    for i, _ in enumerate(texts):
        vec = [0.0] * len(texts)
        vec[i] = 1.0
        result.append(vec)
    return result


def _identical_embed(texts: list[str]) -> list[list[float]]:
    """Return the same unit vector for every text — zero distance everywhere."""
    return [[1.0, 0.0] for _ in texts]


def _block_embed(block_size: int):
    """Return identical vectors within each block of block_size sentences."""

    def _embed(texts: list[str]) -> list[list[float]]:
        result = []
        for i, _ in enumerate(texts):
            block = i // block_size
            vec = [0.0] * 8
            vec[block % 8] = 1.0
            result.append(vec)
        return result

    return _embed


# ── internal helpers ──────────────────────────────────────────────────────────


class TestCosine:
    def test_identical_vectors_return_one(self):
        assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_return_neg_one(self):
        assert _cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_magnitude_returns_zero(self):
        assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestBagOfChars:
    def test_returns_one_vector_per_text(self):
        result = _bag_of_chars(["hello", "world"])
        assert len(result) == 2

    def test_each_vector_is_normalised(self):
        result = _bag_of_chars(["abc"])
        mag = math.sqrt(sum(v * v for v in result[0]))
        assert mag == pytest.approx(1.0, abs=1e-6)

    def test_different_texts_produce_different_vectors(self):
        a, b = _bag_of_chars(["aaa", "zzz"])
        assert a != b

    def test_same_text_produces_same_vector(self):
        v1, v2 = _bag_of_chars(["hello"]), _bag_of_chars(["hello"])
        assert v1 == v2


class TestSplitSentences:
    def test_splits_on_period(self):
        parts = _split_sentences("First. Second.")
        assert len(parts) == 2

    def test_strips_whitespace(self):
        parts = _split_sentences("  One.  Two.  ")
        assert all(not p.startswith(" ") for p in parts)


# ── empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string_returns_empty(self):
        chunker = SemanticChunker(_cfg())
        assert chunker.chunk("", doc_id="d") == []

    def test_whitespace_only_returns_empty(self):
        chunker = SemanticChunker(_cfg())
        assert chunker.chunk("   \n  ", doc_id="d") == []


# ── protocol ──────────────────────────────────────────────────────────────────


class TestProtocol:
    def test_satisfies_chunker_protocol(self):
        assert isinstance(SemanticChunker(_cfg()), Chunker)


# ── single sentence ───────────────────────────────────────────────────────────


class TestSingleSentence:
    def test_single_sentence_returns_one_chunk(self):
        chunker = SemanticChunker(_cfg())
        result = chunker.chunk("Only one sentence here.", doc_id="d")
        assert len(result) == 1
        assert "Only one sentence here" in result[0].content


# ── breakpoint detection ──────────────────────────────────────────────────────


class TestBreakpointDetection:
    def test_identical_embeddings_produce_one_chunk(self):
        """When all sentences are identical in embedding space, no split occurs."""
        text = "Sent one. Sent two. Sent three. Sent four."
        chunker = SemanticChunker(_cfg(threshold=95.0), embed_fn=_identical_embed)
        result = chunker.chunk(text, doc_id="d")
        assert len(result) == 1

    def test_block_boundaries_produce_correct_splits(self):
        """Block-embed with 2 sentences per block → distances alternate [0, 1, 0, 1, 0, 1, 0].
        50th percentile of those 7 distances = 0 → split where d > 0 → 4 chunks."""
        text = " ".join(f"Sent{i}." for i in range(8))
        chunker = SemanticChunker(_cfg(threshold=50.0), embed_fn=_block_embed(2))
        result = chunker.chunk(text, doc_id="d")
        assert len(result) == 4

    def test_block_embed_splits_at_block_boundaries(self):
        """Sentences in the same block share vectors; adjacent blocks differ maximally."""
        # 6 sentences in blocks of 3: sents 0-2 identical, sents 3-5 identical
        text = " ".join(f"Sentence {i}." for i in range(6))
        chunker = SemanticChunker(
            _cfg(threshold=50.0),
            embed_fn=_block_embed(3),
        )
        result = chunker.chunk(text, doc_id="d")
        # Should split into 2 chunks (one per block)
        assert len(result) == 2


# ── threshold strategies ──────────────────────────────────────────────────────


class TestThresholdStrategies:
    def _two_block_text(self) -> str:
        return " ".join(f"S{i}." for i in range(6))

    def test_percentile_threshold(self):
        chunker = SemanticChunker(
            _cfg(breakpoint_type="percentile", threshold=50.0),
            embed_fn=_block_embed(3),
        )
        result = chunker.chunk(self._two_block_text(), doc_id="d")
        assert len(result) == 2

    def test_standard_deviation_threshold(self):
        chunker = SemanticChunker(
            _cfg(breakpoint_type="standard_deviation", threshold=50.0),
            embed_fn=_block_embed(3),
        )
        result = chunker.chunk(self._two_block_text(), doc_id="d")
        # With orthogonal blocks, std-dev threshold should still split
        assert len(result) >= 1  # at least not a hard error

    def test_interquartile_threshold(self):
        chunker = SemanticChunker(
            _cfg(breakpoint_type="interquartile", threshold=75.0),
            embed_fn=_block_embed(3),
        )
        result = chunker.chunk(self._two_block_text(), doc_id="d")
        assert len(result) >= 1


# ── buffer size ───────────────────────────────────────────────────────────────


class TestBufferSize:
    def test_buffer_does_not_crash(self):
        """buffer_size > 0 still produces valid chunks."""
        text = " ".join(f"Sentence {i}." for i in range(6))
        chunker = SemanticChunker(_cfg(buffer=2), embed_fn=_identical_embed)
        result = chunker.chunk(text, doc_id="d")
        assert len(result) >= 1

    def test_buffer_calls_embed_with_correct_count(self):
        """embed_fn is called with exactly len(sentences) items."""
        text = "One. Two. Three."
        seen: list[list[str]] = []

        def capturing_embed(texts: list[str]) -> list[list[float]]:
            seen.append(texts)
            return [[1.0, 0.0]] * len(texts)

        chunker = SemanticChunker(_cfg(buffer=1), embed_fn=capturing_embed)
        chunker.chunk(text, doc_id="d")
        assert len(seen[0]) == 3  # 3 sentences regardless of buffer


# ── fallback embedding ────────────────────────────────────────────────────────


class TestFallbackEmbedding:
    def test_no_embed_fn_uses_bag_of_chars(self):
        """Without inject embed_fn the chunker still produces valid output."""
        text = "Hello world. This is a different topic. Back to normal."
        chunker = SemanticChunker(_cfg())
        result = chunker.chunk(text, doc_id="d")
        assert len(result) >= 1

    def test_result_is_list_of_chunks(self):
        chunker = SemanticChunker(_cfg())
        result = chunker.chunk("One. Two.", doc_id="d")
        assert isinstance(result, list)


# ── chunk fields ──────────────────────────────────────────────────────────────


class TestChunkFields:
    def test_chunk_index_is_sequential(self):
        text = " ".join(f"S{i}." for i in range(6))
        chunker = SemanticChunker(_cfg(threshold=0.0), embed_fn=_orthogonal_embed)
        result = chunker.chunk(text, doc_id="d")
        assert [c.chunk_index for c in result] == list(range(len(result)))

    def test_metadata_contains_doc_id(self):
        chunker = SemanticChunker(_cfg(), embed_fn=_identical_embed)
        result = chunker.chunk("Hello. World.", doc_id="semantic_doc")
        assert result[0].metadata["doc_id"] == "semantic_doc"

    def test_parent_id_is_none(self):
        chunker = SemanticChunker(_cfg(), embed_fn=_identical_embed)
        result = chunker.chunk("Hello. World.", doc_id="d")
        assert result[0].parent_id is None

    def test_level_is_zero(self):
        chunker = SemanticChunker(_cfg(), embed_fn=_identical_embed)
        result = chunker.chunk("Hello. World.", doc_id="d")
        assert result[0].level == 0
