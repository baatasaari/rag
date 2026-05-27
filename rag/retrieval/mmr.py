"""
Maximal Marginal Relevance (MMR) diversity re-ranking.

MMR iteratively selects the next result that maximises:
    λ * relevance(d, q) − (1 − λ) * max_{d' ∈ S} similarity(d, d')

where S is the set of already-selected results.

λ (lambda_param):
    1.0 → pure relevance (no diversity penalty)
    0.0 → pure diversity (always pick the most different remaining result)
    0.5 → balanced (default in MMRConfig)

Similarity between two chunks is approximated as the normalised Jaccard
coefficient over word sets (no embedding required at re-rank time).
"""

from __future__ import annotations

from rag.retrieval.protocols import RetrievalResult


def _jaccard(a: str, b: str) -> float:
    """Normalised Jaccard similarity between two text strings."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def apply_mmr(
    candidates: list[RetrievalResult],
    *,
    top_n: int,
    lambda_param: float = 0.5,
) -> list[RetrievalResult]:
    """Re-rank *candidates* using MMR and return the top_n most diverse results.

    The input list is assumed to be pre-ranked by descending relevance score.
    Output is ranked by MMR selection order (best first).

    Args:
        candidates:    Retrieved results, sorted by descending score.
        top_n:         How many results to return.
        lambda_param:  Trade-off between relevance and diversity [0, 1].
    """
    if not candidates:
        return []
    top_n = min(top_n, len(candidates))

    selected: list[RetrievalResult] = []
    remaining = list(candidates)

    while len(selected) < top_n and remaining:
        if not selected:
            # First pick: highest relevance score.
            best = remaining.pop(0)
        else:
            best_mmr = float("-inf")
            best_idx = 0
            for idx, cand in enumerate(remaining):
                rel = cand.score
                max_sim = max(_jaccard(cand.content, s.content) for s in selected)
                mmr = lambda_param * rel - (1.0 - lambda_param) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx
            best = remaining.pop(best_idx)

        selected.append(
            RetrievalResult(
                chunk_id=best.chunk_id,
                doc_id=best.doc_id,
                content=best.content,
                score=best.score,
                rank=len(selected),
                retrieval_method=best.retrieval_method,
                metadata=best.metadata,
            )
        )

    return selected
