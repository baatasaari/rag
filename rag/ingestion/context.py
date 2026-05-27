"""
IngestionContext — mutable state bag that flows through all 15 pipeline stages.

Each stage receives the context, updates the relevant fields, appends its name
to completed_stages, and returns the same object.  Stages signal a pipeline
abort (e.g. duplicate detected, no valid chunks) by calling ctx.abort().
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from rag.core.schemas import DataClassificationLevel


class IngestionContext(BaseModel):
    """Mutable state carried through the ingestion pipeline."""

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    # ── Input (set by caller before pipeline.run()) ────────────────────────
    source_uri: str
    doc_id: str
    raw_content: bytes | None = None

    # ── Stage 1: validate ──────────────────────────────────────────────────
    mime_type: str = "text/plain"

    # ── Stage 2: extract ───────────────────────────────────────────────────
    text: str = ""

    # ── Stage 3: PII detection ─────────────────────────────────────────────
    pii_types: list[str] = Field(default_factory=list)
    pii_risk_level: str = "none"  # none | low | medium | high

    # ── Stage 4: classification ────────────────────────────────────────────
    classification_level: DataClassificationLevel = DataClassificationLevel.INTERNAL

    # ── Stage 5: sanitise ──────────────────────────────────────────────────
    sanitised_text: str = ""

    # ── Stage 6: deduplicate ───────────────────────────────────────────────
    content_hash: str = ""
    is_duplicate: bool = False

    # ── Stage 7-8: chunk + validate ────────────────────────────────────────
    chunks: list[Any] = Field(default_factory=list)  # list[Chunk]

    # ── Stage 9: embed ─────────────────────────────────────────────────────
    embeddings: list[list[float]] = Field(default_factory=list)

    # ── Stage 10: RBAC ─────────────────────────────────────────────────────
    allowed_roles: list[str] = Field(default_factory=list)

    # ── Pipeline metadata ──────────────────────────────────────────────────
    ingestion_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_stages: list[str] = Field(default_factory=list)
    stage_errors: dict[str, str] = Field(default_factory=dict)
    abort_reason: str | None = None

    # ── Helpers ────────────────────────────────────────────────────────────

    @property
    def should_abort(self) -> bool:
        return self.abort_reason is not None

    @property
    def effective_text(self) -> str:
        """Return sanitised text if available, else raw extracted text."""
        return self.sanitised_text or self.text

    def mark_stage_done(self, stage: str) -> None:
        self.completed_stages.append(stage)

    def abort(self, reason: str) -> None:
        """Signal that the pipeline should stop after the current stage."""
        self.abort_reason = reason


def make_doc_id(source_uri: str) -> str:
    """Deterministic doc_id derived from the source URI (32-char hex digest)."""
    return hashlib.sha256(source_uri.encode()).hexdigest()[:32]
