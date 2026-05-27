"""
Generation Layer — shared data types and structural Protocol.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass
class GeneratedAnswer:
    """Canonical output of any LLM adapter or cache hit."""

    answer: str
    tokens_in: int
    tokens_out: int
    model: str
    provider: str
    cached: bool = False
    latency_ms: float = 0.0
    citations_used: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.citations_used:
            self.citations_used = _extract_citation_indices(self.answer)


_CITATION_RE = re.compile(r"\[(\d+)\]")


def _extract_citation_indices(text: str) -> list[int]:
    """Return sorted unique citation indices found in *text* (e.g. [1], [3])."""
    return sorted({int(m) for m in _CITATION_RE.findall(text)})


@runtime_checkable
class LLMAdapter(Protocol):
    """Structural Protocol satisfied by all LLM provider adapters."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def generate(
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> GeneratedAnswer:
        """Generate a complete response (non-streaming)."""
        ...

    async def stream(  # type: ignore[override]
        self,
        system: str,
        user_message: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """Async-generator yielding response tokens.

        Implementations use ``yield`` internally, so callers iterate directly:
            async for token in adapter.stream(...): ...
        """
        # Protocol stub — concrete adapters are async generator functions.
        return  # type: ignore[return-value]
        yield  # noqa: unreachable — makes this an async generator for type checkers
