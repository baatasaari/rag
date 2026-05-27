"""
Tests for rag.ingestion.context — IngestionContext and make_doc_id.
"""

from __future__ import annotations

from rag.core.schemas import DataClassificationLevel
from rag.ingestion.context import IngestionContext, make_doc_id


# ── make_doc_id ───────────────────────────────────────────────────────────────


class TestMakeDocId:
    def test_returns_32_char_hex(self):
        doc_id = make_doc_id("gs://bucket/doc.pdf")
        assert len(doc_id) == 32
        assert all(c in "0123456789abcdef" for c in doc_id)

    def test_deterministic_for_same_uri(self):
        assert make_doc_id("gs://bucket/doc.pdf") == make_doc_id("gs://bucket/doc.pdf")

    def test_different_uris_produce_different_ids(self):
        assert make_doc_id("gs://bucket/a.pdf") != make_doc_id("gs://bucket/b.pdf")


# ── IngestionContext defaults ─────────────────────────────────────────────────


class TestIngestionContextDefaults:
    def _make(self) -> IngestionContext:
        return IngestionContext(source_uri="gs://bucket/doc.pdf", doc_id="abc123")

    def test_default_mime_type(self):
        assert self._make().mime_type == "text/plain"

    def test_default_text_is_empty(self):
        assert self._make().text == ""

    def test_default_pii_types_empty(self):
        assert self._make().pii_types == []

    def test_default_pii_risk_level(self):
        assert self._make().pii_risk_level == "none"

    def test_default_classification_is_internal(self):
        assert self._make().classification_level == DataClassificationLevel.INTERNAL

    def test_default_is_not_duplicate(self):
        assert self._make().is_duplicate is False

    def test_default_chunks_empty(self):
        assert self._make().chunks == []

    def test_default_embeddings_empty(self):
        assert self._make().embeddings == []

    def test_default_allowed_roles_empty(self):
        assert self._make().allowed_roles == []

    def test_completed_stages_empty(self):
        assert self._make().completed_stages == []

    def test_abort_reason_none(self):
        assert self._make().abort_reason is None

    def test_should_abort_false_by_default(self):
        assert self._make().should_abort is False

    def test_ingestion_timestamp_set(self):
        ctx = self._make()
        assert ctx.ingestion_timestamp is not None


# ── IngestionContext helpers ──────────────────────────────────────────────────


class TestIngestionContextHelpers:
    def test_mark_stage_done_appends(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        ctx.mark_stage_done("validate")
        ctx.mark_stage_done("extract")
        assert ctx.completed_stages == ["validate", "extract"]

    def test_abort_sets_reason(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        ctx.abort("duplicate found")
        assert ctx.abort_reason == "duplicate found"
        assert ctx.should_abort is True

    def test_abort_does_not_clear_completed_stages(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        ctx.mark_stage_done("validate")
        ctx.abort("reason")
        assert "validate" in ctx.completed_stages

    def test_effective_text_prefers_sanitised(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        ctx.text = "raw"
        ctx.sanitised_text = "clean"
        assert ctx.effective_text == "clean"

    def test_effective_text_falls_back_to_text(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        ctx.text = "raw"
        assert ctx.effective_text == "raw"

    def test_effective_text_empty_when_both_empty(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        assert ctx.effective_text == ""

    def test_stage_errors_is_dict(self):
        ctx = IngestionContext(source_uri="u", doc_id="d")
        ctx.stage_errors["validate"] = "bad source_uri"
        assert ctx.stage_errors["validate"] == "bad source_uri"
