"""
Tests for rag.chunking.strategies.hierarchical — HierarchicalChunker.

Verifies parent/child structure, level values, parent_id linkage,
overlap in children, and chunk ordering.

Schema constraints:
  parent_chunk_size >= 128, child_chunk_size >= 64,
  child < parent, overlap < child.
"""

from __future__ import annotations

import pytest

from rag.chunking.protocols import Chunker
from rag.chunking.strategies.hierarchical import HierarchicalChunker
from rag.core.schemas import HierarchicalChunkingConfig


# ── helpers ───────────────────────────────────────────────────────────────────


def _cfg(
    *,
    parent: int = 256,
    child: int = 128,
    overlap: int = 0,
) -> HierarchicalChunkingConfig:
    return HierarchicalChunkingConfig(
        parent_chunk_size=parent,
        child_chunk_size=child,
        overlap=overlap,
    )


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


# ── empty input ───────────────────────────────────────────────────────────────


class TestEmptyInput:
    def test_empty_string_returns_empty(self):
        chunker = HierarchicalChunker(_cfg())
        assert chunker.chunk("", doc_id="d") == []

    def test_whitespace_only_returns_empty(self):
        chunker = HierarchicalChunker(_cfg())
        assert chunker.chunk("  \n  ", doc_id="d") == []


# ── protocol ──────────────────────────────────────────────────────────────────


class TestProtocol:
    def test_satisfies_chunker_protocol(self):
        assert isinstance(HierarchicalChunker(_cfg()), Chunker)


# ── parent / child structure ──────────────────────────────────────────────────


class TestParentChildStructure:
    def test_parents_have_level_one(self):
        # 256 words → exactly 1 parent
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        parents = [c for c in result if c.level == 1]
        assert len(parents) == 1

    def test_children_have_level_zero(self):
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        children = [c for c in result if c.level == 0]
        assert len(children) >= 1

    def test_parent_has_no_parent_id(self):
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        parents = [c for c in result if c.level == 1]
        for p in parents:
            assert p.parent_id is None

    def test_children_reference_correct_parent_id(self):
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="mydoc")
        children = [c for c in result if c.level == 0]
        expected_parent_id = "mydoc:parent:0"
        for child in children:
            assert child.parent_id == expected_parent_id

    def test_multiple_parents_have_distinct_ids(self):
        # 512 words, parent_size=256 → 2 parents
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(512), doc_id="doc")
        parents = [c for c in result if c.level == 1]
        parent_ids_referenced = set(c.parent_id for c in result if c.level == 0)
        assert len(parents) == 2
        assert len(parent_ids_referenced) == 2

    def test_single_word_produces_parent_and_child(self):
        chunker = HierarchicalChunker(_cfg())
        result = chunker.chunk("hello", doc_id="d")
        assert any(c.level == 1 for c in result)
        assert any(c.level == 0 for c in result)


# ── chunk ordering ────────────────────────────────────────────────────────────


class TestChunkOrdering:
    def test_parent_precedes_its_children(self):
        """Each parent chunk must appear before its children in the output list."""
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        for chunk in result:
            if chunk.level == 1:
                p_id = f"d:parent:{chunk.metadata['parent_index']}"
                matching_children = [c for c in result if c.parent_id == p_id]
                for child in matching_children:
                    assert child.chunk_index > chunk.chunk_index

    def test_chunk_index_is_globally_sequential(self):
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        assert [c.chunk_index for c in result] == list(range(len(result)))


# ── overlap ───────────────────────────────────────────────────────────────────


class TestOverlap:
    def test_child_overlap_repeats_words(self):
        # child=128, overlap=64 → step=64; adjacent children share 64 words
        chunker = HierarchicalChunker(_cfg(parent=512, child=128, overlap=64))
        result = chunker.chunk(_words(512), doc_id="d")
        children = [c for c in result if c.level == 0 and c.parent_id == "d:parent:0"]
        if len(children) >= 2:
            tail = children[0].content.split()[-64:]
            head = children[1].content.split()[:64]
            assert tail == head

    def test_no_overlap_children_are_non_overlapping(self):
        # child=128, overlap=0 → step=128; no repeated words
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        children = [c for c in result if c.level == 0 and c.parent_id == "d:parent:0"]
        if len(children) >= 2:
            words_c0 = set(children[0].content.split())
            words_c1 = set(children[1].content.split())
            assert words_c0.isdisjoint(words_c1)

    def test_correct_child_count_with_overlap(self):
        # 256 words per parent, child=128, overlap=64, step=64
        # children at positions 0,64,128,192 → 4 children
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=64))
        result = chunker.chunk(_words(256), doc_id="d")
        children = [c for c in result if c.level == 0 and c.parent_id == "d:parent:0"]
        assert len(children) == 4


# ── content correctness ───────────────────────────────────────────────────────


class TestContentCorrectness:
    def test_parent_content_is_superset_of_children_words(self):
        """All words in children should be present in the parent."""
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        parents = {c.metadata["parent_index"]: c for c in result if c.level == 1}
        children_by_parent: dict[int, list] = {}
        for c in result:
            if c.level == 0:
                p_idx = c.metadata["parent_index"]
                children_by_parent.setdefault(p_idx, []).append(c)

        for p_idx, parent_chunk in parents.items():
            parent_words = set(parent_chunk.content.split())
            for child in children_by_parent.get(p_idx, []):
                for w in child.content.split():
                    assert w in parent_words

    def test_metadata_contains_doc_id(self):
        chunker = HierarchicalChunker(_cfg(parent=128, child=64, overlap=0))
        result = chunker.chunk(_words(128), doc_id="thedoc")
        for chunk in result:
            assert chunk.metadata["doc_id"] == "thedoc"

    def test_two_children_without_overlap(self):
        # 256 words, child=128, overlap=0 → exactly 2 children per parent
        chunker = HierarchicalChunker(_cfg(parent=256, child=128, overlap=0))
        result = chunker.chunk(_words(256), doc_id="d")
        children = [c for c in result if c.level == 0]
        assert len(children) == 2
        assert len(children[0].content.split()) == 128
        assert len(children[1].content.split()) == 128
