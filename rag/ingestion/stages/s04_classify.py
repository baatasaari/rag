"""
Stage 4: Document Classification

Determines the data sensitivity level of the document:
  PUBLIC → INTERNAL → CONFIDENTIAL → RESTRICTED

Classification logic (in priority order):
  1. If the document text contains classification-marker keywords, use the
     highest marker found.
  2. If PII risk is "high" and current classification < CONFIDENTIAL, escalate.
  3. If no markers and no PII escalation, use the configured default (INTERNAL).

Sets ctx.classification_level (DataClassificationLevel).
"""

from __future__ import annotations

from rag.core.schemas import DataClassificationLevel
from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

# Priority order: highest to lowest.
_CLASSIFICATION_ORDER = [
    DataClassificationLevel.RESTRICTED,
    DataClassificationLevel.CONFIDENTIAL,
    DataClassificationLevel.INTERNAL,
    DataClassificationLevel.PUBLIC,
]

_KEYWORDS: dict[DataClassificationLevel, list[str]] = {
    DataClassificationLevel.RESTRICTED: [
        "restricted",
        "board only",
        "c-suite only",
        "not for distribution",
        "top secret",
    ],
    DataClassificationLevel.CONFIDENTIAL: [
        "confidential",
        "sensitive",
        "internal only",
        "for internal use",
        "do not distribute",
    ],
    DataClassificationLevel.INTERNAL: [
        "internal",
        "staff only",
        "employee",
        "for lbg use",
    ],
    DataClassificationLevel.PUBLIC: [],
}


def classify(
    ctx: IngestionContext,
    *,
    default: DataClassificationLevel = DataClassificationLevel.INTERNAL,
) -> IngestionContext:
    """Classify document sensitivity and set ctx.classification_level."""
    text_lower = (ctx.effective_text or "").lower()

    level = _keyword_classify(text_lower)

    if level is None:
        level = default

    # Escalate if PII risk is high and below CONFIDENTIAL.
    if ctx.pii_risk_level == "high" and _level_index(level) > _level_index(
        DataClassificationLevel.CONFIDENTIAL
    ):
        level = DataClassificationLevel.CONFIDENTIAL

    ctx.classification_level = level
    log.info(
        "ingestion.classify.ok",
        source_uri=ctx.source_uri,
        classification_level=level.value,
    )
    return ctx


def _keyword_classify(text_lower: str) -> DataClassificationLevel | None:
    for level in _CLASSIFICATION_ORDER:
        for kw in _KEYWORDS[level]:
            if kw in text_lower:
                return level
    return None


def _level_index(level: DataClassificationLevel) -> int:
    """Lower index = higher classification."""
    return _CLASSIFICATION_ORDER.index(level)
