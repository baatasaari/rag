"""
Citation extraction and formatting.

CitationBuilder converts retrieval results into structured Citation objects.
The formatter then renders those citations into string form suitable for
appending to the assembled prompt.

Citation modes (CitationMode):
    INLINE   — [1], [2] markers embedded in the context block header, with a
               footnote list appended after the context section.
    FOOTNOTE — a numbered reference list appended after all context.  No inline
               markers in the context block itself.
    NONE     — no citations produced; Citation objects still exist for tracing
               but render as empty strings.

FCA / data-handling:
    Only source_uri, title, page, and doc_id are surfaced.
    Classification level and RBAC roles are NEVER exposed in citations.
"""

from __future__ import annotations

from rag.core.schemas import CitationMode
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span
from rag.retrieval.protocols import RetrievalResult
from rag.augmentation.protocols import Citation

log = get_logger(__name__)

_SNIPPET_LEN = 120


def _snippet(text: str) -> str:
    text = text.strip()
    if len(text) <= _SNIPPET_LEN:
        return text
    return text[:_SNIPPET_LEN].rsplit(" ", 1)[0] + " …"


class CitationBuilder:
    """Builds Citation objects from retrieval results."""

    def __init__(self, mode: CitationMode = CitationMode.INLINE) -> None:
        self._mode = mode

    def build(self, results: list[RetrievalResult]) -> list[Citation]:
        """Produce one Citation per result, 1-based indexed."""
        with record_span(
            "augmentation.citations",
            **{
                RAGAttributes.CITATION_COUNT: len(results),
                "rag.citation.mode": self._mode.value,
            },
        ):
            citations = [self._from_result(i + 1, r) for i, r in enumerate(results)]
            log.info("augmentation.citations.built", count=len(citations), mode=self._mode.value)
            return citations

    def _from_result(self, index: int, r: RetrievalResult) -> Citation:
        meta = r.metadata or {}
        return Citation(
            index=index,
            chunk_id=r.chunk_id,
            doc_id=r.doc_id,
            source_uri=str(meta.get("source_uri", meta.get("source", ""))),
            title=str(meta.get("title", r.doc_id)),
            page=meta.get("page"),
            mode=self._mode,
            snippet=_snippet(r.content),
        )

    # ── formatting helpers ────────────────────────────────────────────────────

    @staticmethod
    def format_inline_marker(citation: Citation) -> str:
        """Return '[N]' for INLINE mode, empty string otherwise."""
        if citation.mode == CitationMode.INLINE:
            return f"[{citation.index}]"
        return ""

    @staticmethod
    def format_footnote_list(citations: list[Citation]) -> str:
        """Return a formatted footnote block for INLINE and FOOTNOTE modes."""
        if not citations or citations[0].mode == CitationMode.NONE:
            return ""
        lines = []
        for c in citations:
            parts = [f"[{c.index}]", c.title or c.doc_id]
            if c.source_uri:
                parts.append(f"<{c.source_uri}>")
            if c.page is not None:
                parts.append(f"p.{c.page}")
            lines.append(" ".join(parts))
        return "\n".join(lines)
