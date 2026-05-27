"""
Stage 3: PII Detection

Scans ctx.effective_text for UK-relevant PII patterns using compiled regexes.

FCA compliance rules enforced here:
  - Log the TYPE of PII found — NEVER the VALUE.
  - Risk level is derived from the count of distinct PII types found.
  - If PIIDetectionConfig.emit_audit_event is True, the pipeline's audit
    stage will record a PII_DETECTED event (handled in Stage 15).

Sets ctx.pii_types (list of PII type names) and ctx.pii_risk_level.
"""

from __future__ import annotations

import re

from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

# ── UK-relevant PII patterns ──────────────────────────────────────────────────
# These detect the PRESENCE of PII — they are never used to extract the VALUE.

_PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL_ADDRESS": re.compile(
        r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
    ),
    "PHONE_NUMBER": re.compile(
        r"(?<!\d)(?:\+44|0)[\d\s\-\(\)]{9,15}(?!\d)"
    ),
    "NI_NUMBER": re.compile(
        r"\b[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]\b", re.IGNORECASE
    ),
    "SORT_CODE": re.compile(r"\b\d{2}[\-\s]\d{2}[\-\s]\d{2}\b"),
    "ACCOUNT_NUMBER": re.compile(r"\b\d{8}\b"),
    "UK_POSTCODE": re.compile(
        r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b", re.IGNORECASE
    ),
    "DATE_OF_BIRTH": re.compile(
        r"\b(?:0?[1-9]|[12]\d|3[01])[\/\-\.](?:0?[1-9]|1[0-2])[\/\-\.](?:19|20)\d{2}\b"
    ),
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"),
}

_RISK_THRESHOLDS = {
    "high": 5,    # 5+ distinct PII types
    "medium": 3,  # 3-4 distinct PII types
    "low": 1,     # 1-2 distinct PII types
}


def detect_pii(ctx: IngestionContext) -> IngestionContext:
    """Detect PII types in the document text.

    Sets ctx.pii_types and ctx.pii_risk_level.

    Security:  Only the TYPE of PII is logged and stored.
               The matched VALUE is never extracted or logged.
    """
    text = ctx.effective_text
    found: list[str] = [
        pii_type for pii_type, pattern in _PII_PATTERNS.items() if pattern.search(text)
    ]

    ctx.pii_types = found
    ctx.pii_risk_level = _classify_risk(len(found))

    # Log type only — NEVER the matched value.
    log.info(
        "ingestion.pii_detected",
        source_uri=ctx.source_uri,
        pii_types=found,          # only type names, safe to log
        pii_risk_level=ctx.pii_risk_level,
    )
    return ctx


def _classify_risk(n_types: int) -> str:
    if n_types >= _RISK_THRESHOLDS["high"]:
        return "high"
    if n_types >= _RISK_THRESHOLDS["medium"]:
        return "medium"
    if n_types >= _RISK_THRESHOLDS["low"]:
        return "low"
    return "none"
