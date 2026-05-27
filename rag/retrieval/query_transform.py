"""
Query Transformation — HyDE, step-back, multi-query, sub-query.

Each transformation takes a raw query string and an embedding callable,
then returns one or more transformed queries that broaden retrieval coverage.

LLM-dependent transforms (HyDE, step-back, multi-query) accept a `generate_fn`
callable:
    async def generate_fn(prompt: str) -> str

This keeps the retrieval layer decoupled from the generation layer.
The generation engine wires the Gemini client in at startup.

Transforms are applied in the order:
    step_back  →  multi_query  →  HyDE  →  sub_query

Each transform is additive — its outputs are merged with the original query
pool.  The caller deduplicates embeddings before retrieval.
"""

from __future__ import annotations

from typing import Callable, Awaitable

from rag.core.schemas import QueryTransformationConfig
from rag.observability.logging import get_logger

log = get_logger(__name__)

GenerateFn = Callable[[str], Awaitable[str]]


async def step_back(query: str, generate_fn: GenerateFn) -> str:
    """Generate a more abstract, step-back version of the query."""
    prompt = (
        "You are an expert at query reformulation. "
        "Given the specific question below, generate a broader, more general "
        "question that, when answered, would help answer the specific one.\n\n"
        f"Specific question: {query}\n\n"
        "Broader question:"
    )
    result = await generate_fn(prompt)
    return result.strip()


async def multi_query(
    query: str,
    generate_fn: GenerateFn,
    count: int = 3,
) -> list[str]:
    """Generate `count` semantically diverse paraphrases of the query."""
    prompt = (
        f"Generate {count} distinct paraphrases of the following question. "
        "Each should approach the topic from a different angle. "
        "Output one paraphrase per line with no numbering or extra text.\n\n"
        f"Question: {query}"
    )
    result = await generate_fn(prompt)
    lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
    return lines[:count]


async def hyde(query: str, generate_fn: GenerateFn) -> str:
    """Generate a hypothetical document that would answer the query (HyDE).

    The hypothetical document's embedding is used for retrieval rather than
    the query embedding.  Effective for corpora where query and document
    embedding spaces diverge (e.g., regulatory Q&A).
    """
    prompt = (
        "Write a short paragraph (3-5 sentences) that directly and accurately "
        "answers the following question as if you were an expert. "
        "Do not say 'I don't know'. Write a plausible, informative answer.\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )
    result = await generate_fn(prompt)
    return result.strip()


async def apply_transformations(
    query: str,
    config: QueryTransformationConfig,
    generate_fn: GenerateFn,
) -> list[str]:
    """Return a deduplicated list of query strings after all enabled transforms.

    The original query is always the first element.
    """
    queries: list[str] = [query]

    if config.step_back:
        try:
            sb = await step_back(query, generate_fn)
            if sb and sb not in queries:
                queries.append(sb)
        except Exception as exc:
            log.warning("retrieval.query_transform.step_back_failed", error=str(exc))

    if config.multi_query:
        try:
            variants = await multi_query(query, generate_fn, count=config.multi_query_count)
            for v in variants:
                if v and v not in queries:
                    queries.append(v)
        except Exception as exc:
            log.warning("retrieval.query_transform.multi_query_failed", error=str(exc))

    if config.hyde:
        try:
            hyp_doc = await hyde(query, generate_fn)
            if hyp_doc and hyp_doc not in queries:
                queries.append(hyp_doc)
        except Exception as exc:
            log.warning("retrieval.query_transform.hyde_failed", error=str(exc))

    log.info(
        "retrieval.query_transform.complete",
        original=query,
        total_queries=len(queries),
    )
    return queries
