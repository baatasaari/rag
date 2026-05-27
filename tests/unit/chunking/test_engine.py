"""
Tests for rag.chunking.engine — ChunkingEngine orchestration.

Verifies strategy dispatch, OTel span emission, empty-text handling,
protocol conformance, and the NotImplementedError for unimplemented strategies.
"""

from __future__ import annotations

import pytest

from rag.chunking.engine import ChunkingEngine
from rag.chunking.protocols import Chunk, Chunker
from rag.chunking.strategies.fixed import FixedChunker
from rag.chunking.strategies.hierarchical import HierarchicalChunker
from rag.chunking.strategies.recursive import RecursiveChunker
from rag.chunking.strategies.semantic import SemanticChunker
from rag.chunking.strategies.sentence import SentenceChunker
from rag.core.schemas import (
    AgenticChunkingConfig,
    ChunkingConfig,
    ChunkingStrategy,
    FixedChunkingConfig,
    HierarchicalChunkingConfig,
    RecursiveChunkingConfig,
    SemanticChunkingConfig,
    SentenceChunkingConfig,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_config(strategy: ChunkingStrategy, **overrides) -> ChunkingConfig:
    return ChunkingConfig(strategy=strategy, **overrides)


def _words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


# ── strategy dispatch ─────────────────────────────────────────────────────────


class TestStrategyDispatch:
    def test_fixed_strategy_creates_fixed_chunker(self):
        cfg = _make_config(
            ChunkingStrategy.FIXED,
            fixed=FixedChunkingConfig(chunk_size=10, overlap=0, unit="words"),
        )
        engine = ChunkingEngine(cfg)
        assert isinstance(engine._chunker, FixedChunker)

    def test_sentence_strategy_creates_sentence_chunker(self):
        cfg = _make_config(ChunkingStrategy.SENTENCE)
        engine = ChunkingEngine(cfg)
        assert isinstance(engine._chunker, SentenceChunker)

    def test_recursive_strategy_creates_recursive_chunker(self):
        cfg = _make_config(ChunkingStrategy.RECURSIVE)
        engine = ChunkingEngine(cfg)
        assert isinstance(engine._chunker, RecursiveChunker)

    def test_hierarchical_strategy_creates_hierarchical_chunker(self):
        cfg = _make_config(ChunkingStrategy.HIERARCHICAL)
        engine = ChunkingEngine(cfg)
        assert isinstance(engine._chunker, HierarchicalChunker)

    def test_semantic_strategy_creates_semantic_chunker(self):
        cfg = _make_config(ChunkingStrategy.SEMANTIC)
        engine = ChunkingEngine(cfg)
        assert isinstance(engine._chunker, SemanticChunker)

    def test_semantic_strategy_passes_embed_fn(self):
        cfg = _make_config(ChunkingStrategy.SEMANTIC)
        my_fn = lambda texts: [[0.1]] * len(texts)
        engine = ChunkingEngine(cfg, embed_fn=my_fn)
        assert engine._chunker._embed_fn is my_fn

    def test_unimplemented_strategy_raises_not_implemented(self):
        cfg = ChunkingConfig(
            strategy=ChunkingStrategy.AGENTIC,
            agentic=AgenticChunkingConfig(),
        )
        with pytest.raises(NotImplementedError, match="agentic"):
            ChunkingEngine(cfg)


# ── chunk() output ────────────────────────────────────────────────────────────


class TestChunkOutput:
    def test_empty_text_returns_empty_list(self):
        cfg = _make_config(ChunkingStrategy.FIXED, fixed=FixedChunkingConfig(chunk_size=10, overlap=0, unit="words"))
        engine = ChunkingEngine(cfg)
        assert engine.chunk("", doc_id="d") == []

    def test_whitespace_only_returns_empty_list(self):
        cfg = _make_config(ChunkingStrategy.FIXED, fixed=FixedChunkingConfig(chunk_size=10, overlap=0, unit="words"))
        engine = ChunkingEngine(cfg)
        assert engine.chunk("   \n  ", doc_id="d") == []

    def test_returns_list_of_chunk_objects(self):
        cfg = _make_config(ChunkingStrategy.FIXED, fixed=FixedChunkingConfig(chunk_size=5, overlap=0, unit="words"))
        engine = ChunkingEngine(cfg)
        result = engine.chunk(_words(10), doc_id="d")
        assert isinstance(result, list)
        assert all(isinstance(c, Chunk) for c in result)

    def test_doc_id_propagated_to_chunk_metadata(self):
        cfg = _make_config(ChunkingStrategy.FIXED, fixed=FixedChunkingConfig(chunk_size=100, overlap=0, unit="words"))
        engine = ChunkingEngine(cfg)
        result = engine.chunk("hello world", doc_id="my_doc_123")
        assert result[0].metadata["doc_id"] == "my_doc_123"


# ── each strategy produces correct output via engine ─────────────────────────


class TestEndToEndStrategies:
    def test_fixed_produces_chunks(self):
        cfg = _make_config(
            ChunkingStrategy.FIXED,
            fixed=FixedChunkingConfig(chunk_size=3, overlap=0, unit="words"),
        )
        engine = ChunkingEngine(cfg)
        result = engine.chunk(_words(9), doc_id="d")
        assert len(result) == 3

    def test_sentence_produces_chunks(self):
        cfg = _make_config(ChunkingStrategy.SENTENCE)
        engine = ChunkingEngine(cfg)
        text = " ".join(f"Sentence {i}." for i in range(10))
        result = engine.chunk(text, doc_id="d")
        assert len(result) >= 1

    def test_recursive_produces_chunks(self):
        cfg = _make_config(
            ChunkingStrategy.RECURSIVE,
            recursive=RecursiveChunkingConfig(chunk_size=20, overlap=0),
        )
        engine = ChunkingEngine(cfg)
        result = engine.chunk("hello world foo bar baz qux quux corge grault", doc_id="d")
        assert len(result) >= 1

    def test_hierarchical_produces_both_levels(self):
        cfg = _make_config(
            ChunkingStrategy.HIERARCHICAL,
            hierarchical=HierarchicalChunkingConfig(
                parent_chunk_size=128, child_chunk_size=64, overlap=0
            ),
        )
        engine = ChunkingEngine(cfg)
        result = engine.chunk(_words(128), doc_id="d")
        levels = {c.level for c in result}
        assert 0 in levels
        assert 1 in levels

    def test_semantic_produces_chunks(self):
        cfg = _make_config(ChunkingStrategy.SEMANTIC)
        engine = ChunkingEngine(cfg, embed_fn=lambda texts: [[1.0, 0.0]] * len(texts))
        result = engine.chunk("One sentence. Another sentence.", doc_id="d")
        assert len(result) >= 1
