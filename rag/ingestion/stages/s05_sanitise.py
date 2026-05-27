"""
Stage 5: Content Sanitisation

Normalises the extracted text before chunking:
  - Unicode NFKC normalisation (e.g. ligatures, half-width chars)
  - Strip C0/C1 control characters (keep \\n and \\t)
  - Collapse runs of spaces/tabs to a single space
  - Collapse 3+ consecutive newlines to two (paragraph break)
  - Strip leading/trailing whitespace

Sets ctx.sanitised_text.  Always succeeds — it operates on ctx.text which
is guaranteed non-empty by the time we reach this stage.
"""

from __future__ import annotations

import re
import unicodedata

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

# Matches C0 and C1 control characters except LF (\x0a) and HT (\x09).
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def sanitise(ctx: IngestionContext) -> IngestionContext:
    """Normalise and clean ctx.text, writing the result to ctx.sanitised_text."""
    text = ctx.text

    # 1. Unicode NFKC — resolves ligatures, half-width chars, compatibility forms.
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove control characters (keep \n and \t).
    text = _CTRL_RE.sub("", text)

    # 3. Collapse horizontal whitespace.
    text = _MULTI_SPACE_RE.sub(" ", text)

    # 4. Normalise paragraph spacing.
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    ctx.sanitised_text = text.strip()
    log.info(
        "ingestion.sanitise.ok",
        source_uri=ctx.source_uri,
        char_count=len(ctx.sanitised_text),
    )
    return ctx
