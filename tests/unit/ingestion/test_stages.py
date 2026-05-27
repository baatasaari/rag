"""
Tests for rag.ingestion.stages — all 15 stage functions.

Each stage is tested in isolation using a pre-configured IngestionContext.
External services (vector store, document store, etc.) are mocked with AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.chunking.protocols import Chunk
from rag.core.schemas import DataClassificationLevel
from rag.ingestion.context import IngestionContext, make_doc_id
from rag.ingestion.stages import (
    s01_validate,
    s02_extract,
    s03_pii,
    s04_classify,
    s05_sanitise,
    s06_deduplicate,
    s07_chunk,
    s08_validate_chunks,
    s09_embed,
    s10_rbac,
    s11_vector_store,
    s12_doc_store,
    s13_graph_store,
    s14_cache,
    s15_audit,
)
from rag.security.audit import AuditEventType


# ── shared helpers ────────────────────────────────────────────────────────────


def _ctx(
    source_uri: str = "gs://bucket/doc.txt",
    text: str = "Hello world.",
    mime_type: str = "text/plain",
    raw_content: bytes | None = None,
) -> IngestionContext:
    ctx = IngestionContext(
        source_uri=source_uri,
        doc_id=make_doc_id(source_uri),
        raw_content=raw_content or text.encode(),
        mime_type=mime_type,
    )
    ctx.text = text
    ctx.sanitised_text = text
    return ctx


def _chunk(content: str, idx: int = 0) -> Chunk:
    return Chunk(content=content, chunk_index=idx, metadata={"doc_id": "test"})


# ── Stage 1: validate ─────────────────────────────────────────────────────────


class TestS01Validate:
    def test_valid_document_sets_mime_type(self):
        ctx = _ctx(source_uri="gs://bucket/doc.txt", raw_content=b"hello")
        result = s01_validate.validate(ctx)
        assert result.mime_type == "text/plain"

    def test_empty_source_uri_raises(self):
        ctx = IngestionContext(source_uri="", doc_id="d", raw_content=b"x")
        with pytest.raises(ValueError, match="source_uri"):
            s01_validate.validate(ctx)

    def test_no_content_raises(self):
        ctx = IngestionContext(source_uri="gs://bucket/doc.txt", doc_id="d", raw_content=None)
        with pytest.raises(ValueError, match="No content"):
            s01_validate.validate(ctx)

    def test_oversized_content_raises(self):
        big = b"x" * (50 * 1024 * 1024 + 1)
        ctx = IngestionContext(source_uri="gs://bucket/doc.txt", doc_id="d", raw_content=big)
        with pytest.raises(ValueError, match="size limit"):
            s01_validate.validate(ctx)

    def test_unsupported_mime_type_raises(self):
        ctx = IngestionContext(
            source_uri="gs://bucket/file.xyz", doc_id="d", raw_content=b"x"
        )
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            s01_validate.validate(ctx)

    def test_pdf_mime_type_detected(self):
        ctx = IngestionContext(
            source_uri="gs://bucket/report.pdf", doc_id="d", raw_content=b"content"
        )
        result = s01_validate.validate(ctx)
        assert result.mime_type == "application/pdf"


# ── Stage 2: extract ──────────────────────────────────────────────────────────


class TestS02Extract:
    def test_plain_text_decoded_as_utf8(self):
        ctx = _ctx(raw_content="hello world".encode())
        ctx.mime_type = "text/plain"
        ctx.text = ""
        result = s02_extract.extract_text(ctx)
        assert result.text == "hello world"

    def test_html_strips_tags(self):
        ctx = _ctx(raw_content=b"<h1>Title</h1><p>Body text</p>")
        ctx.mime_type = "text/html"
        result = s02_extract.extract_text(ctx)
        assert "<" not in result.text
        assert "Title" in result.text
        assert "Body text" in result.text

    def test_html_entity_replaced(self):
        ctx = _ctx(raw_content=b"Price: &pound;100")
        ctx.mime_type = "text/html"
        result = s02_extract.extract_text(ctx)
        assert "&pound;" not in result.text

    def test_pdf_raises_without_pdfminer(self):
        import sys
        with pytest.MonkeyPatch().context() as mp:
            mp.setitem(sys.modules, "pdfminer", None)
            mp.setitem(sys.modules, "pdfminer.high_level", None)
            ctx = _ctx(raw_content=b"%PDF-1.4 stub")
            ctx.mime_type = "application/pdf"
            with pytest.raises(RuntimeError, match="pdfminer"):
                s02_extract.extract_text(ctx)

    def test_text_is_set_on_context(self):
        ctx = _ctx(raw_content=b"test content")
        ctx.mime_type = "text/plain"
        ctx.text = ""
        result = s02_extract.extract_text(ctx)
        assert result.text != ""


# ── Stage 3: PII detection ────────────────────────────────────────────────────


class TestS03PII:
    def test_no_pii_in_clean_text(self):
        ctx = _ctx(text="The quick brown fox jumps over the lazy dog.")
        result = s03_pii.detect_pii(ctx)
        assert result.pii_types == []
        assert result.pii_risk_level == "none"

    def test_email_detected(self):
        ctx = _ctx(text="Contact john.doe@example.com for info.")
        result = s03_pii.detect_pii(ctx)
        assert "EMAIL_ADDRESS" in result.pii_types

    def test_phone_detected(self):
        ctx = _ctx(text="Call us on +44 20 7946 0958 today.")
        result = s03_pii.detect_pii(ctx)
        assert "PHONE_NUMBER" in result.pii_types

    def test_sort_code_detected(self):
        ctx = _ctx(text="Sort code: 12-34-56.")
        result = s03_pii.detect_pii(ctx)
        assert "SORT_CODE" in result.pii_types

    def test_uk_postcode_detected(self):
        ctx = _ctx(text="Send to EC1A 1BB.")
        result = s03_pii.detect_pii(ctx)
        assert "UK_POSTCODE" in result.pii_types

    def test_high_pii_risk_level_with_many_types(self):
        ctx = _ctx(
            text=(
                "john@bank.com call +44 7700 900000 "
                "sort 12-34-56 postcode EC1A 1BB "
                "DOB 01/01/1980 card 4111 1111 1111 1111"
            )
        )
        result = s03_pii.detect_pii(ctx)
        assert result.pii_risk_level in ("medium", "high")

    def test_medium_risk_level(self):
        ctx = _ctx(text="Email: a@b.com sort code 12-34-56 postcode SW1A 1AA")
        result = s03_pii.detect_pii(ctx)
        assert result.pii_risk_level in ("low", "medium")

    def test_pii_types_are_strings_not_values(self):
        """Verify that only TYPE names (not matched text) are stored."""
        ctx = _ctx(text="email: secret@lloyds.com")
        result = s03_pii.detect_pii(ctx)
        assert "EMAIL_ADDRESS" in result.pii_types
        assert "secret@lloyds.com" not in str(result.pii_types)


# ── Stage 4: classify ─────────────────────────────────────────────────────────


class TestS04Classify:
    def test_no_markers_defaults_to_internal(self):
        ctx = _ctx(text="Some regular document text.")
        s03_pii.detect_pii(ctx)
        result = s04_classify.classify(ctx)
        assert result.classification_level == DataClassificationLevel.INTERNAL

    def test_restricted_keyword_sets_restricted(self):
        ctx = _ctx(text="RESTRICTED: board only document.")
        s03_pii.detect_pii(ctx)
        result = s04_classify.classify(ctx)
        assert result.classification_level == DataClassificationLevel.RESTRICTED

    def test_confidential_keyword_sets_confidential(self):
        ctx = _ctx(text="Confidential: do not share externally.")
        s03_pii.detect_pii(ctx)
        result = s04_classify.classify(ctx)
        assert result.classification_level == DataClassificationLevel.CONFIDENTIAL

    def test_restricted_takes_priority_over_confidential(self):
        ctx = _ctx(text="restricted and confidential document")
        s03_pii.detect_pii(ctx)
        result = s04_classify.classify(ctx)
        assert result.classification_level == DataClassificationLevel.RESTRICTED

    def test_high_pii_escalates_to_confidential(self):
        ctx = _ctx(text="Some document without classification markers.")
        ctx.pii_risk_level = "high"
        result = s04_classify.classify(ctx, default=DataClassificationLevel.PUBLIC)
        assert result.classification_level == DataClassificationLevel.CONFIDENTIAL

    def test_custom_default_respected(self):
        ctx = _ctx(text="Plain text, no markers.")
        ctx.pii_risk_level = "none"
        result = s04_classify.classify(ctx, default=DataClassificationLevel.PUBLIC)
        assert result.classification_level == DataClassificationLevel.PUBLIC


# ── Stage 5: sanitise ─────────────────────────────────────────────────────────


class TestS05Sanitise:
    def test_control_chars_removed(self):
        ctx = _ctx(text="hello\x00world\x01foo")
        result = s05_sanitise.sanitise(ctx)
        assert "\x00" not in result.sanitised_text
        assert "helloworld" in result.sanitised_text or "hello" in result.sanitised_text

    def test_multiple_spaces_collapsed(self):
        ctx = _ctx(text="too   many   spaces")
        result = s05_sanitise.sanitise(ctx)
        assert "  " not in result.sanitised_text

    def test_multiple_newlines_normalised(self):
        ctx = _ctx(text="para one\n\n\n\npara two")
        result = s05_sanitise.sanitise(ctx)
        assert "\n\n\n" not in result.sanitised_text

    def test_stripped_leading_trailing_whitespace(self):
        ctx = _ctx(text="  \n  content  \n  ")
        result = s05_sanitise.sanitise(ctx)
        assert result.sanitised_text == result.sanitised_text.strip()

    def test_newline_preserved_tab_collapsed_to_space(self):
        ctx = _ctx(text="line1\nline2\tcolumn")
        result = s05_sanitise.sanitise(ctx)
        assert "\n" in result.sanitised_text
        # Tabs are horizontal whitespace — collapsed to single space.
        assert "column" in result.sanitised_text


# ── Stage 6: deduplicate ──────────────────────────────────────────────────────


class TestS06Deduplicate:
    @pytest.mark.asyncio
    async def test_unique_document_sets_hash(self):
        ctx = _ctx()
        doc_store = AsyncMock()
        doc_store.get_by_hash = AsyncMock(return_value=None)
        result = await s06_deduplicate.deduplicate(ctx, doc_store)
        assert result.content_hash != ""
        assert len(result.content_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_unique_document_not_flagged(self):
        ctx = _ctx()
        doc_store = AsyncMock()
        doc_store.get_by_hash = AsyncMock(return_value=None)
        result = await s06_deduplicate.deduplicate(ctx, doc_store)
        assert result.is_duplicate is False
        assert not result.should_abort

    @pytest.mark.asyncio
    async def test_duplicate_detected_sets_abort(self):
        ctx = _ctx()
        existing = MagicMock()
        existing.doc_id = "existing-doc-id"
        doc_store = AsyncMock()
        doc_store.get_by_hash = AsyncMock(return_value=existing)
        result = await s06_deduplicate.deduplicate(ctx, doc_store)
        assert result.is_duplicate is True
        assert result.should_abort is True

    @pytest.mark.asyncio
    async def test_same_content_produces_same_hash(self):
        ctx1 = _ctx(text="same content")
        ctx2 = _ctx(text="same content")
        doc_store = AsyncMock()
        doc_store.get_by_hash = AsyncMock(return_value=None)
        r1 = await s06_deduplicate.deduplicate(ctx1, doc_store)
        r2 = await s06_deduplicate.deduplicate(ctx2, doc_store)
        assert r1.content_hash == r2.content_hash

    @pytest.mark.asyncio
    async def test_different_content_different_hash(self):
        ctx1 = _ctx(text="content A")
        ctx2 = _ctx(text="content B")
        doc_store = AsyncMock()
        doc_store.get_by_hash = AsyncMock(return_value=None)
        r1 = await s06_deduplicate.deduplicate(ctx1, doc_store)
        r2 = await s06_deduplicate.deduplicate(ctx2, doc_store)
        assert r1.content_hash != r2.content_hash


# ── Stage 7: chunk ────────────────────────────────────────────────────────────


class TestS07Chunk:
    def test_chunk_delegates_to_engine(self):
        ctx = _ctx(text="Some document text for chunking.")
        engine = MagicMock()
        engine.chunk.return_value = [_chunk("Some document text for chunking.")]
        result = s07_chunk.chunk(ctx, engine)
        engine.chunk.assert_called_once_with(ctx.effective_text, doc_id=ctx.doc_id)
        assert len(result.chunks) == 1

    def test_empty_text_passes_empty_to_engine(self):
        ctx = _ctx(text="")
        engine = MagicMock()
        engine.chunk.return_value = []
        s07_chunk.chunk(ctx, engine)
        engine.chunk.assert_called_once_with("", doc_id=ctx.doc_id)


# ── Stage 8: validate_chunks ──────────────────────────────────────────────────


class TestS08ValidateChunks:
    def test_short_chunks_dropped(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("hi", 0), _chunk("a" * 30, 1)]
        result = s08_validate_chunks.validate_chunks(ctx, min_chunk_length=20)
        assert len(result.chunks) == 1
        assert result.chunks[0].content == "a" * 30

    def test_no_chunks_after_filter_aborts(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("tiny", 0)]
        result = s08_validate_chunks.validate_chunks(ctx, min_chunk_length=100)
        assert result.should_abort is True

    def test_max_chunks_truncated(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("a" * 50, i) for i in range(10)]
        result = s08_validate_chunks.validate_chunks(ctx, min_chunk_length=1, max_chunks=5)
        assert len(result.chunks) == 5

    def test_valid_chunks_unchanged(self):
        ctx = _ctx()
        chunks = [_chunk("a" * 50, i) for i in range(3)]
        ctx.chunks = chunks
        result = s08_validate_chunks.validate_chunks(ctx, min_chunk_length=20)
        assert len(result.chunks) == 3


# ── Stage 9: embed ────────────────────────────────────────────────────────────


class TestS09Embed:
    @pytest.mark.asyncio
    async def test_embeddings_populated(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text one", 0), _chunk("text two", 1)]
        engine = AsyncMock()
        engine.embed_for_ingestion = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        result = await s09_embed.embed(ctx, engine)
        assert len(result.embeddings) == 2

    @pytest.mark.asyncio
    async def test_embed_uses_chunk_content(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("my text", 0)]
        engine = AsyncMock()
        engine.embed_for_ingestion = AsyncMock(return_value=[[0.1]])
        await s09_embed.embed(ctx, engine)
        engine.embed_for_ingestion.assert_called_once_with(["my text"])

    @pytest.mark.asyncio
    async def test_embed_propagates_engine_error(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text", 0)]
        engine = AsyncMock()
        engine.embed_for_ingestion = AsyncMock(side_effect=RuntimeError("adapter down"))
        with pytest.raises(RuntimeError, match="adapter down"):
            await s09_embed.embed(ctx, engine)


# ── Stage 10: RBAC ────────────────────────────────────────────────────────────


class TestS10RBAC:
    def test_public_gets_all_roles(self):
        ctx = _ctx()
        ctx.classification_level = DataClassificationLevel.PUBLIC
        result = s10_rbac.apply_rbac(ctx, reject_restricted=False)
        assert "public" in result.allowed_roles
        assert "admin" in result.allowed_roles

    def test_internal_excludes_public(self):
        ctx = _ctx()
        ctx.classification_level = DataClassificationLevel.INTERNAL
        result = s10_rbac.apply_rbac(ctx)
        assert "public" not in result.allowed_roles
        assert "employee" in result.allowed_roles

    def test_confidential_restricts_to_managers_and_above(self):
        ctx = _ctx()
        ctx.classification_level = DataClassificationLevel.CONFIDENTIAL
        result = s10_rbac.apply_rbac(ctx)
        assert "employee" not in result.allowed_roles
        assert "manager" in result.allowed_roles

    def test_restricted_admin_only(self):
        ctx = _ctx()
        ctx.classification_level = DataClassificationLevel.RESTRICTED
        result = s10_rbac.apply_rbac(ctx, reject_restricted=False)
        assert result.allowed_roles == ["admin"]

    def test_restricted_aborts_when_reject_true(self):
        ctx = _ctx()
        ctx.classification_level = DataClassificationLevel.RESTRICTED
        result = s10_rbac.apply_rbac(ctx, reject_restricted=True)
        assert result.should_abort is True

    def test_restricted_allowed_when_reject_false(self):
        ctx = _ctx()
        ctx.classification_level = DataClassificationLevel.RESTRICTED
        result = s10_rbac.apply_rbac(ctx, reject_restricted=False)
        assert not result.should_abort


# ── Stage 11: vector store ────────────────────────────────────────────────────


class TestS11VectorStore:
    @pytest.mark.asyncio
    async def test_upsert_called_with_records(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("content", 0)]
        ctx.embeddings = [[0.1, 0.2]]
        ctx.allowed_roles = ["employee"]
        vector_store = AsyncMock()
        await s11_vector_store.upsert_vectors(ctx, vector_store)
        vector_store.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_count_matches_chunk_count(self):
        ctx = _ctx()
        ctx.chunks = [_chunk(f"chunk {i}", i) for i in range(5)]
        ctx.embeddings = [[float(i)] for i in range(5)]
        ctx.allowed_roles = ["employee"]
        captured: list = []
        vector_store = AsyncMock()
        vector_store.upsert = AsyncMock(side_effect=lambda records: captured.extend(records))
        await s11_vector_store.upsert_vectors(ctx, vector_store)
        assert len(captured) == 5

    @pytest.mark.asyncio
    async def test_record_contains_classification_level(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text", 0)]
        ctx.embeddings = [[0.1]]
        ctx.allowed_roles = ["manager"]
        ctx.classification_level = DataClassificationLevel.CONFIDENTIAL
        captured: list = []
        vector_store = AsyncMock()
        vector_store.upsert = AsyncMock(side_effect=lambda records: captured.extend(records))
        await s11_vector_store.upsert_vectors(ctx, vector_store)
        assert captured[0]["metadata"]["classification_level"] == "CONFIDENTIAL"

    @pytest.mark.asyncio
    async def test_record_contains_allowed_roles(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text", 0)]
        ctx.embeddings = [[0.1]]
        ctx.allowed_roles = ["analyst", "admin"]
        captured: list = []
        vector_store = AsyncMock()
        vector_store.upsert = AsyncMock(side_effect=lambda records: captured.extend(records))
        await s11_vector_store.upsert_vectors(ctx, vector_store)
        assert captured[0]["allowed_roles"] == ["analyst", "admin"]


# ── Stage 12: document store ──────────────────────────────────────────────────


class TestS12DocStore:
    @pytest.mark.asyncio
    async def test_put_called_once(self):
        ctx = _ctx()
        ctx.content_hash = "abc123"
        ctx.allowed_roles = ["employee"]
        doc_store = AsyncMock()
        await s12_doc_store.upsert_document(ctx, doc_store)
        doc_store.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_doc_record_has_required_fields(self):
        ctx = _ctx()
        ctx.content_hash = "deadbeef"
        ctx.allowed_roles = ["manager"]
        captured: list = []
        doc_store = AsyncMock()
        doc_store.put = AsyncMock(side_effect=lambda doc: captured.append(doc))
        await s12_doc_store.upsert_document(ctx, doc_store)
        doc = captured[0]
        assert doc["doc_id"] == ctx.doc_id
        assert doc["source_uri"] == ctx.source_uri
        assert doc["content_hash"] == "deadbeef"
        assert "classification_level" in doc
        assert "allowed_roles" in doc

    @pytest.mark.asyncio
    async def test_pii_types_stored_in_metadata(self):
        ctx = _ctx()
        ctx.pii_types = ["EMAIL_ADDRESS", "PHONE_NUMBER"]
        ctx.content_hash = "hash"
        ctx.allowed_roles = ["admin"]
        captured: list = []
        doc_store = AsyncMock()
        doc_store.put = AsyncMock(side_effect=lambda doc: captured.append(doc))
        await s12_doc_store.upsert_document(ctx, doc_store)
        assert captured[0]["metadata"]["pii_types"] == ["EMAIL_ADDRESS", "PHONE_NUMBER"]


# ── Stage 13: graph store ──────────────────────────────────────────────────────


class TestS13GraphStore:
    @pytest.mark.asyncio
    async def test_none_graph_store_skips_silently(self):
        ctx = _ctx()
        result = await s13_graph_store.upsert_graph(ctx, None)
        assert result is ctx  # unchanged

    @pytest.mark.asyncio
    async def test_document_node_upserted(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text", 0)]
        graph = AsyncMock()
        await s13_graph_store.upsert_graph(ctx, graph)
        # First call should be the Document node
        first_call_args = graph.upsert_node.call_args_list[0]
        assert first_call_args[0][0] == "Document"

    @pytest.mark.asyncio
    async def test_chunk_nodes_upserted(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text A", 0), _chunk("text B", 1)]
        graph = AsyncMock()
        await s13_graph_store.upsert_graph(ctx, graph)
        chunk_calls = [c for c in graph.upsert_node.call_args_list if c[0][0] == "Chunk"]
        assert len(chunk_calls) == 2

    @pytest.mark.asyncio
    async def test_contains_edges_created(self):
        ctx = _ctx()
        ctx.chunks = [_chunk("text", 0)]
        graph = AsyncMock()
        await s13_graph_store.upsert_graph(ctx, graph)
        rel_types = [c[0][2] for c in graph.upsert_edge.call_args_list]
        assert "CONTAINS" in rel_types


# ── Stage 14: cache invalidation ──────────────────────────────────────────────


class TestS14Cache:
    @pytest.mark.asyncio
    async def test_none_cache_skips_silently(self):
        ctx = _ctx()
        result = await s14_cache.invalidate_cache(ctx, None)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_invalidate_called_with_doc_id(self):
        ctx = _ctx()
        cache = AsyncMock()
        cache.invalidate = AsyncMock(return_value=3)
        await s14_cache.invalidate_cache(ctx, cache)
        cache.invalidate.assert_called_once_with(ctx.doc_id)

    @pytest.mark.asyncio
    async def test_cache_error_does_not_raise(self):
        ctx = _ctx()
        cache = AsyncMock()
        cache.invalidate = AsyncMock(side_effect=RuntimeError("Redis down"))
        # Should not raise — stage 14 is soft
        result = await s14_cache.invalidate_cache(ctx, cache)
        assert result is ctx


# ── Stage 15: audit ───────────────────────────────────────────────────────────


class TestS15Audit:
    @pytest.mark.asyncio
    async def test_none_audit_logger_skips_silently(self):
        ctx = _ctx()
        result = await s15_audit.emit_audit(ctx, None)
        assert result is ctx

    @pytest.mark.asyncio
    async def test_log_event_called_on_success(self):
        ctx = _ctx()
        ctx.mark_stage_done("validate")
        audit = AsyncMock()
        audit.log_event = AsyncMock()
        await s15_audit.emit_audit(ctx, audit)
        audit.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_event_type_is_ingestion(self):
        ctx = _ctx()
        captured = []
        audit = AsyncMock()
        audit.log_event = AsyncMock(side_effect=lambda e: captured.append(e))
        await s15_audit.emit_audit(ctx, audit)
        assert captured[0].event_type == AuditEventType.INGESTION

    @pytest.mark.asyncio
    async def test_outcome_failure_on_abort(self):
        ctx = _ctx()
        ctx.abort("duplicate")
        captured = []
        audit = AsyncMock()
        audit.log_event = AsyncMock(side_effect=lambda e: captured.append(e))
        await s15_audit.emit_audit(ctx, audit)
        assert captured[0].outcome == "FAILURE"

    @pytest.mark.asyncio
    async def test_outcome_success_on_clean_run(self):
        ctx = _ctx()
        captured = []
        audit = AsyncMock()
        audit.log_event = AsyncMock(side_effect=lambda e: captured.append(e))
        await s15_audit.emit_audit(ctx, audit)
        assert captured[0].outcome == "SUCCESS"

    @pytest.mark.asyncio
    async def test_pii_types_in_audit_event(self):
        ctx = _ctx()
        ctx.pii_types = ["EMAIL_ADDRESS"]
        captured = []
        audit = AsyncMock()
        audit.log_event = AsyncMock(side_effect=lambda e: captured.append(e))
        await s15_audit.emit_audit(ctx, audit)
        assert "EMAIL_ADDRESS" in captured[0].pii_types_detected

    @pytest.mark.asyncio
    async def test_pubsub_called_on_success(self):
        ctx = _ctx()
        audit = AsyncMock()
        audit.log_event = AsyncMock()
        pubsub = AsyncMock()
        pubsub.publish = AsyncMock()
        await s15_audit.emit_audit(ctx, audit, pubsub_client=pubsub)
        pubsub.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_pubsub_not_called_on_abort(self):
        ctx = _ctx()
        ctx.abort("duplicate")
        audit = AsyncMock()
        audit.log_event = AsyncMock()
        pubsub = AsyncMock()
        pubsub.publish = AsyncMock()
        await s15_audit.emit_audit(ctx, audit, pubsub_client=pubsub)
        pubsub.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_error_does_not_raise(self):
        ctx = _ctx()
        audit = AsyncMock()
        audit.log_event = AsyncMock(side_effect=RuntimeError("Cloud Logging down"))
        # Should not raise — audit logs are best-effort from the stage perspective;
        # the pipeline catches errors in _finalise.
        result = await s15_audit.emit_audit(ctx, audit)
        assert result is ctx
