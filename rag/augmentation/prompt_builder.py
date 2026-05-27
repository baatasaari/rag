"""
Prompt Builder — assembles the final LLM prompt from retrieved context.

Layout (INLINE citation mode):
┌─────────────────────────────────────────────────────┐
│  {system_prompt}                                    │
│                                                     │
│  --- CONTEXT ---                                    │
│  [1] <title>                                        │
│  {compressed_chunk_1}                               │
│                                                     │
│  [2] <title>                                        │
│  {compressed_chunk_2}                               │
│  …                                                  │
│  --- END CONTEXT ---                                │
│                                                     │
│  --- SOURCES ---                                    │
│  [1] Title <uri>                                    │
│  [2] Title <uri>                                    │
│  --- END SOURCES ---                                │
│                                                     │
│  Question: {query}                                  │
│  Answer:                                            │
└─────────────────────────────────────────────────────┘

Context window management:
    If the assembled context exceeds `max_chars`, chunks are dropped from the
    bottom (lowest-ranked) until it fits.  The query and system prompt are
    never truncated.

System prompt templates:
    "lbg-default" produces a conservative, compliance-aware system prompt.
    Pass any other string to use it verbatim as the system prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag.augmentation.citations import CitationBuilder
from rag.augmentation.protocols import AugmentedContext, Citation
from rag.core.schemas import CitationMode
from rag.observability.logging import get_logger
from rag.observability.tracing import record_span

log = get_logger(__name__)

_DEFAULT_MAX_CHARS = 24_000   # ~6 k tokens at 4 chars/token
_LBG_SYSTEM_PROMPT = """\
You are an intelligent assistant for Lloyds Banking Group (LBG).
Answer questions using ONLY the provided context.
If the context does not contain enough information to answer, say so.
Do not speculate or add information that is not in the context.
Always cite the source reference numbers [N] when using information from a context block.
Comply with FCA and internal data-handling policies at all times.\
"""


@dataclass
class AssembledPrompt:
    system: str
    context_block: str  # includes chunk text + citation markers
    sources_block: str  # footnote list
    user_message: str   # query phrasing
    total_chars: int
    chunks_included: int
    chunks_dropped: int


class PromptBuilder:
    """Builds the final prompt from compressed chunks and citations."""

    def __init__(
        self,
        system_template: str = "lbg-default",
        max_chars: int = _DEFAULT_MAX_CHARS,
    ) -> None:
        self._system = (
            _LBG_SYSTEM_PROMPT if system_template == "lbg-default" else system_template
        )
        self._max_chars = max_chars

    def build(self, ctx: AugmentedContext) -> AssembledPrompt:
        """Assemble the prompt, truncating low-ranked chunks if needed."""
        with record_span("augmentation.prompt_builder") as span:
            context_block, sources_block, included, dropped = self._assemble_context(ctx)
            user_message = f"Question: {ctx.query}\nAnswer:"

            total = len(self._system) + len(context_block) + len(sources_block) + len(user_message)

            span.set_attribute("rag.prompt.chunks_included", included)
            span.set_attribute("rag.prompt.chunks_dropped", dropped)
            span.set_attribute("rag.prompt.total_chars", total)

            log.info(
                "augmentation.prompt_builder.built",
                chunks_included=included,
                chunks_dropped=dropped,
                total_chars=total,
            )
            return AssembledPrompt(
                system=self._system,
                context_block=context_block,
                sources_block=sources_block,
                user_message=user_message,
                total_chars=total,
                chunks_included=included,
                chunks_dropped=dropped,
            )

    def _assemble_context(
        self, ctx: AugmentedContext
    ) -> tuple[str, str, int, int]:
        """Build context and sources blocks, dropping trailing chunks if over limit."""
        budget = self._max_chars - len(self._system) - len(ctx.query) - 200  # headroom

        included_chunks: list[str] = []
        included_citations: list[Citation] = []
        dropped = 0

        for i, (chunk, citation) in enumerate(zip(ctx.compressed_chunks, ctx.citations)):
            block = self._format_chunk_block(chunk, citation)
            if budget - len(block) < 0 and included_chunks:
                # Drop this and all remaining chunks.
                dropped = len(ctx.compressed_chunks) - i
                break
            included_chunks.append(block)
            included_citations.append(citation)
            budget -= len(block)

        context_body = "\n\n".join(included_chunks)
        context_block = f"--- CONTEXT ---\n{context_body}\n--- END CONTEXT ---" if context_body else ""
        sources_block = self._format_sources(included_citations)

        return context_block, sources_block, len(included_chunks), dropped

    @staticmethod
    def _format_chunk_block(chunk: str, citation: Citation) -> str:
        marker = CitationBuilder.format_inline_marker(citation)
        header = f"{marker} {citation.title}".strip() if citation.title else marker
        return f"{header}\n{chunk}" if header else chunk

    @staticmethod
    def _format_sources(citations: list[Citation]) -> str:
        footnotes = CitationBuilder.format_footnote_list(citations)
        if not footnotes:
            return ""
        return f"--- SOURCES ---\n{footnotes}\n--- END SOURCES ---"

    def full_prompt(self, ctx: AugmentedContext) -> str:
        """Convenience: return the complete prompt as a single string."""
        p = self.build(ctx)
        parts = [p.system]
        if p.context_block:
            parts.append(p.context_block)
        if p.sources_block:
            parts.append(p.sources_block)
        parts.append(p.user_message)
        return "\n\n".join(parts)
