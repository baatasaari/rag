"""
Context Compression — three strategies for reducing retrieved content size.

LLM_EXTRACT   (default):
    Asks the LLM to extract only the sentences directly relevant to the query.
    Each chunk is sent individually (avoids cross-contamination).
    Requires a generate_fn callable.

SENTENCE_WINDOW:
    Pure-Python: splits the chunk into sentences, keeps every sentence that
    overlaps with at least one query term (case-insensitive), plus a
    configurable context window of ±N surrounding sentences.
    No LLM required — safe to use in latency-sensitive code paths.

MAP_REDUCE:
    Splits large chunks into fixed-length segments, runs LLM_EXTRACT on each
    segment (map), then concatenates the surviving sentences (reduce).
    Falls back to SENTENCE_WINDOW if generate_fn is None.

FCA safe-handling:
    The generate_fn receives only the chunk text, never metadata that reveals
    classification level or RBAC membership.  Callers must ensure the chunk
    text has already been PII-sanitised (done by the ingestion pipeline).
"""

from __future__ import annotations

import asyncio
import re
from typing import Callable, Awaitable

from rag.core.schemas import CompressionStrategy, ContextCompressionConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import record_span

log = get_logger(__name__)

GenerateFn = Callable[[str], Awaitable[str]]

_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
_DEFAULT_WINDOW = 1       # sentences of context either side of a hit
_MAP_REDUCE_SEGMENT = 800  # chars per segment for MAP_REDUCE


# ── sentence-window helper ────────────────────────────────────────────────────


def _sentence_window(query: str, text: str, window: int = _DEFAULT_WINDOW) -> str:
    """Keep sentences that contain any query term, plus ±window neighbours."""
    if not text.strip():
        return text

    q_terms = {t.lower() for t in query.split() if len(t) > 2}
    sentences = _SENTENCE_PATTERN.split(text.strip())
    if not sentences:
        return text

    hits: set[int] = set()
    for i, s in enumerate(sentences):
        lower_s = s.lower()
        if any(t in lower_s for t in q_terms):
            for j in range(max(0, i - window), min(len(sentences), i + window + 1)):
                hits.add(j)

    if not hits:
        # Fall back to first two sentences when no overlap found.
        return " ".join(sentences[:2])

    kept = [sentences[i] for i in sorted(hits)]
    return " ".join(kept)


# ── LLM-based single-chunk compression ───────────────────────────────────────


async def _llm_extract(query: str, chunk: str, generate_fn: GenerateFn) -> str:
    prompt = (
        "Extract only the sentences from the PASSAGE below that are directly "
        f"relevant to the QUESTION. Output extracted sentences only — no "
        "explanations, no commentary, no new information.\n\n"
        f"QUESTION: {query}\n\n"
        f"PASSAGE:\n{chunk}\n\n"
        "EXTRACTED:"
    )
    result = await generate_fn(prompt)
    extracted = result.strip()
    return extracted if extracted else chunk  # fall back to original if LLM returns empty


# ── ContextCompressor ─────────────────────────────────────────────────────────


class ContextCompressor:
    """Compresses retrieved chunk texts using the configured strategy."""

    def __init__(
        self,
        config: ContextCompressionConfig,
        generate_fn: GenerateFn | None = None,
    ) -> None:
        self._config = config
        self._generate_fn = generate_fn

    async def compress(self, query: str, chunks: list[str]) -> list[str]:
        if not self._config.enabled or not chunks:
            return chunks

        with record_span(
            "augmentation.compress",
            **{"rag.compression.strategy": self._config.strategy.value},
        ) as span:
            strategy = self._config.strategy
            if strategy == CompressionStrategy.LLM_EXTRACT and self._generate_fn:
                results = await self._llm_extract_all(query, chunks)
            elif strategy == CompressionStrategy.MAP_REDUCE:
                results = await self._map_reduce_all(query, chunks)
            else:
                results = [_sentence_window(query, c) for c in chunks]

            total_in = sum(len(c) for c in chunks)
            total_out = sum(len(r) for r in results)
            span.set_attribute("rag.compression.chars_in", total_in)
            span.set_attribute("rag.compression.chars_out", total_out)
            log.info(
                "augmentation.compress.complete",
                strategy=self._config.strategy.value,
                chunks=len(chunks),
                chars_in=total_in,
                chars_out=total_out,
            )
            return results

    async def _llm_extract_all(self, query: str, chunks: list[str]) -> list[str]:
        assert self._generate_fn is not None
        tasks = [_llm_extract(query, c, self._generate_fn) for c in chunks]
        return list(await asyncio.gather(*tasks))

    async def _map_reduce_all(self, query: str, chunks: list[str]) -> list[str]:
        results = []
        for chunk in chunks:
            if len(chunk) <= _MAP_REDUCE_SEGMENT or self._generate_fn is None:
                results.append(_sentence_window(query, chunk))
            else:
                segments = [
                    chunk[i : i + _MAP_REDUCE_SEGMENT]
                    for i in range(0, len(chunk), _MAP_REDUCE_SEGMENT)
                ]
                extracted = await asyncio.gather(
                    *[_llm_extract(query, seg, self._generate_fn) for seg in segments]
                )
                results.append(" ".join(e for e in extracted if e))
        return results
