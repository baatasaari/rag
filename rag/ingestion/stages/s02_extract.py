"""
Stage 2: Text Extraction

Extracts plain text from raw_content based on ctx.mime_type:
  - text/plain, text/markdown, text/csv, application/json → UTF-8 decode
  - text/html  → strip tags with a lightweight regex (no BS4 dependency)
  - application/pdf → pdfminer.six if installed, else raise
  - application/vnd...docx / application/msword → python-docx if installed, else raise

Sets ctx.text.  Raises RuntimeError if the MIME type requires an optional
library that is not installed.
"""

from __future__ import annotations

import re

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")


def extract_text(ctx: IngestionContext) -> IngestionContext:
    """Extract plain text from ctx.raw_content.

    Sets ctx.text.  Raises RuntimeError if extraction fails.
    """
    mime = ctx.mime_type
    content = ctx.raw_content or b""

    if mime in ("text/plain", "text/markdown", "text/csv", "application/json"):
        ctx.text = _decode_utf8(content)

    elif mime == "text/html":
        ctx.text = _extract_html(content)

    elif mime == "application/pdf":
        ctx.text = _extract_pdf(content)

    elif mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        ctx.text = _extract_docx(content)

    else:
        # Fallback: attempt UTF-8, ignore errors
        ctx.text = content.decode("utf-8", errors="replace")

    log.info(
        "ingestion.extract.ok",
        source_uri=ctx.source_uri,
        mime_type=mime,
        char_count=len(ctx.text),
    )
    return ctx


# ── format-specific extractors ────────────────────────────────────────────────


def _decode_utf8(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _extract_html(content: bytes) -> str:
    text = content.decode("utf-8", errors="replace")
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def _extract_pdf(content: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text as _pdf_extract  # noqa: PLC0415
        import io  # noqa: PLC0415

        return _pdf_extract(io.BytesIO(content)) or ""
    except ImportError as exc:
        raise RuntimeError(
            "PDF extraction requires pdfminer.six. "
            "Install with: pip install pdfminer.six"
        ) from exc


def _extract_docx(content: bytes) -> str:
    try:
        import io  # noqa: PLC0415

        import docx  # noqa: PLC0415

        doc = docx.Document(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs)
    except ImportError as exc:
        raise RuntimeError(
            "DOCX extraction requires python-docx. "
            "Install with: pip install python-docx"
        ) from exc
