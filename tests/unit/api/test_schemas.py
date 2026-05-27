"""
Tests for rag.api.schemas — request/response validation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rag.api.schemas import (
    CitationResponse,
    ErrorResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    ReadyResponse,
)


# ── QueryRequest ──────────────────────────────────────────────────────────────

class TestQueryRequest:
    def _req(self, **overrides) -> QueryRequest:
        defaults = {"query": "What is the policy?", "user_id": "u1", "roles": ["employee"]}
        defaults.update(overrides)
        return QueryRequest(**defaults)

    def test_valid_request(self):
        r = self._req()
        assert r.query == "What is the policy?"
        assert r.roles == ["employee"]

    def test_query_stripped(self):
        r = self._req(query="  hello world  ")
        assert r.query == "hello world"

    def test_blank_query_raises(self):
        with pytest.raises(ValidationError):
            self._req(query="   ")

    def test_empty_query_raises(self):
        with pytest.raises(ValidationError):
            self._req(query="")

    def test_query_too_long_raises(self):
        with pytest.raises(ValidationError):
            self._req(query="x" * 2001)

    def test_empty_roles_raises(self):
        with pytest.raises(ValidationError):
            self._req(roles=[])

    def test_top_k_none_allowed(self):
        r = self._req(top_k=None)
        assert r.top_k is None

    def test_top_k_valid(self):
        r = self._req(top_k=10)
        assert r.top_k == 10

    def test_top_k_zero_raises(self):
        with pytest.raises(ValidationError):
            self._req(top_k=0)

    def test_top_k_over_200_raises(self):
        with pytest.raises(ValidationError):
            self._req(top_k=201)

    def test_session_id_optional(self):
        r = self._req(session_id="sess-abc")
        assert r.session_id == "sess-abc"

    def test_filters_optional(self):
        r = self._req(filters={"doc_type": "policy"})
        assert r.filters == {"doc_type": "policy"}

    def test_multiple_roles(self):
        r = self._req(roles=["employee", "manager", "compliance"])
        assert len(r.roles) == 3


# ── IngestRequest ─────────────────────────────────────────────────────────────

class TestIngestRequest:
    def test_valid(self):
        r = IngestRequest(source_uri="gs://bucket/doc.pdf", roles=["ingest"])
        assert r.source_uri == "gs://bucket/doc.pdf"
        assert r.doc_type == "auto"

    def test_empty_uri_raises(self):
        with pytest.raises(ValidationError):
            IngestRequest(source_uri="", roles=["ingest"])

    def test_default_metadata_empty(self):
        r = IngestRequest(source_uri="gs://x/y.pdf")
        assert r.metadata == {}

    def test_custom_metadata(self):
        r = IngestRequest(source_uri="gs://x/y.pdf", metadata={"region": "UK"})
        assert r.metadata["region"] == "UK"


# ── QueryResponse ─────────────────────────────────────────────────────────────

class TestQueryResponse:
    def test_valid(self):
        r = QueryResponse(
            query_id="qid1", answer="The answer is [1].",
            citations=[], cached=False, tokens_in=80, tokens_out=30,
            latency_ms=250.0, model="gemini", provider="vertex_ai",
            chunks_retrieved=5, chunks_used=3,
        )
        assert r.query_id == "qid1"
        assert r.cached is False

    def test_citations_list(self):
        c = CitationResponse(index=1, title="Doc A", source_uri="gs://x/y.pdf")
        r = QueryResponse(
            query_id="q", answer="ans", citations=[c], cached=True,
            tokens_in=0, tokens_out=0, latency_ms=10.0,
            model="m", provider="p", chunks_retrieved=1, chunks_used=1,
        )
        assert r.citations[0].title == "Doc A"


# ── CitationResponse ──────────────────────────────────────────────────────────

class TestCitationResponse:
    def test_page_optional(self):
        c = CitationResponse(index=1, title="Doc", source_uri="gs://x")
        assert c.page is None

    def test_page_set(self):
        c = CitationResponse(index=2, title="Doc", source_uri="gs://x", page=42)
        assert c.page == 42


# ── HealthResponse / ReadyResponse ────────────────────────────────────────────

class TestHealthResponse:
    def test_ok_status(self):
        h = HealthResponse(status="ok", version="1.0.0", checks={})
        assert h.status == "ok"

    def test_degraded_status(self):
        h = HealthResponse(status="degraded", version="1.0.0", checks={"cache": False})
        assert h.checks["cache"] is False


class TestReadyResponse:
    def test_ready_true(self):
        r = ReadyResponse(ready=True, details={"pipeline": "ok"})
        assert r.ready is True

    def test_ready_false(self):
        r = ReadyResponse(ready=False, details={"pipeline": "not_initialised"})
        assert r.ready is False
        assert r.details["pipeline"] == "not_initialised"


# ── ErrorResponse ─────────────────────────────────────────────────────────────

class TestErrorResponse:
    def test_basic(self):
        e = ErrorResponse(error="Something failed", code="INTERNAL_ERROR")
        assert e.code == "INTERNAL_ERROR"
        assert e.request_id is None

    def test_with_request_id(self):
        e = ErrorResponse(error="fail", code="ERR", request_id="req-123")
        assert e.request_id == "req-123"
