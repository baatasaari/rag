"""
Tests for rag.api.routes.query — POST /v1/query and POST /v1/query/stream.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from rag.api.app import create_app
from rag.api.dependencies import get_pipeline
from rag.augmentation.protocols import Citation
from rag.core.schemas import CitationMode
from rag.generation.protocols import GeneratedAnswer
from rag.pipeline.result import RAGResult
from rag.retrieval.protocols import RetrievalResult


# ── helpers ───────────────────────────────────────────────────────────────────

def _rag_result(answer: str = "The policy requires [1] compliance.") -> RAGResult:
    citation = Citation(
        index=1, chunk_id="c1", doc_id="d1",
        source_uri="gs://bucket/doc.pdf", title="Policy Doc",
        page=None, mode=CitationMode.INLINE, snippet="snippet",
    )
    return RAGResult(
        query_id="test-qid",
        query="What is the policy?",
        answer=answer,
        citations=[citation],
        retrieval_results=[],
        chunks_retrieved=5,
        chunks_used=3,
        tokens_in=80,
        tokens_out=30,
        cached=False,
        provider="vertex_ai",
        model="gemini",
        latency_ms=250.0,
        citations_used=[1],
    )


def _make_client(result: RAGResult | None = None):
    pipeline = AsyncMock()
    pipeline.query = AsyncMock(return_value=result or _rag_result())

    async def _fake_stream(ctx):
        for w in ["The ", "policy ", "applies."]:
            yield w

    pipeline.stream_query = MagicMock(return_value=_fake_stream(None))

    app = create_app(pipeline=pipeline)
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    return TestClient(app), pipeline


_QUERY_BODY = {
    "query": "What is the policy?",
    "user_id": "user1",
    "roles": ["employee"],
}


# ── POST /v1/query ────────────────────────────────────────────────────────────

class TestQueryEndpoint:
    def test_returns_200(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json=_QUERY_BODY)
        assert resp.status_code == 200

    def test_response_schema(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json=_QUERY_BODY)
        body = resp.json()
        assert "answer" in body
        assert "citations" in body
        assert "query_id" in body
        assert "tokens_in" in body
        assert "tokens_out" in body
        assert "latency_ms" in body
        assert "cached" in body

    def test_answer_in_response(self):
        client, _ = _make_client(_rag_result("Compliance is required [1]."))
        resp = client.post("/v1/query", json=_QUERY_BODY)
        assert "Compliance is required" in resp.json()["answer"]

    def test_citations_in_response(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json=_QUERY_BODY)
        citations = resp.json()["citations"]
        assert len(citations) == 1
        assert citations[0]["index"] == 1
        assert citations[0]["title"] == "Policy Doc"

    def test_invalid_query_empty_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json={**_QUERY_BODY, "query": "  "})
        assert resp.status_code == 422

    def test_empty_roles_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json={**_QUERY_BODY, "roles": []})
        assert resp.status_code == 422

    def test_top_k_forwarded(self):
        client, pipeline = _make_client()
        client.post("/v1/query", json={**_QUERY_BODY, "top_k": 3})
        ctx = pipeline.query.call_args[0][0]
        assert ctx.top_k == 3

    def test_roles_become_frozenset(self):
        client, pipeline = _make_client()
        client.post("/v1/query", json={**_QUERY_BODY, "roles": ["employee", "manager"]})
        ctx = pipeline.query.call_args[0][0]
        assert isinstance(ctx.allowed_roles, frozenset)
        assert "employee" in ctx.allowed_roles

    def test_filters_forwarded(self):
        client, pipeline = _make_client()
        body = {**_QUERY_BODY, "filters": {"doc_type": "policy"}}
        client.post("/v1/query", json=body)
        ctx = pipeline.query.call_args[0][0]
        assert ctx.filters == {"doc_type": "policy"}

    def test_pipeline_error_returns_500(self):
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(side_effect=RuntimeError("LLM failed"))
        app = create_app(pipeline=pipeline)
        app.dependency_overrides[get_pipeline] = lambda: pipeline
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/query", json=_QUERY_BODY)
        assert resp.status_code == 500

    def test_request_id_echoed_in_headers(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json=_QUERY_BODY,
                           headers={"X-Request-ID": "my-req-id"})
        assert resp.headers.get("X-Request-ID") == "my-req-id"

    def test_request_id_generated_when_absent(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json=_QUERY_BODY)
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_chunks_fields_in_response(self):
        client, _ = _make_client()
        resp = client.post("/v1/query", json=_QUERY_BODY)
        body = resp.json()
        assert body["chunks_retrieved"] == 5
        assert body["chunks_used"] == 3


# ── POST /v1/query/stream ─────────────────────────────────────────────────────

class TestQueryStreamEndpoint:
    def test_returns_200(self):
        client, _ = _make_client()
        resp = client.post("/v1/query/stream", json=_QUERY_BODY)
        assert resp.status_code == 200

    def test_content_type_is_event_stream(self):
        client, _ = _make_client()
        resp = client.post("/v1/query/stream", json=_QUERY_BODY)
        assert "text/event-stream" in resp.headers["content-type"]

    def test_sse_contains_data_lines(self):
        client, _ = _make_client()
        resp = client.post("/v1/query/stream", json=_QUERY_BODY)
        assert "data:" in resp.text

    def test_sse_ends_with_done_sentinel(self):
        client, _ = _make_client()
        resp = client.post("/v1/query/stream", json=_QUERY_BODY)
        assert "[DONE]" in resp.text

    def test_invalid_query_returns_422(self):
        client, _ = _make_client()
        resp = client.post("/v1/query/stream", json={**_QUERY_BODY, "query": ""})
        assert resp.status_code == 422
