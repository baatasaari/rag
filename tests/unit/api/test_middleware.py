"""
Tests for rag.api.middleware — RequestIDMiddleware and LoggingMiddleware.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from rag.api.app import create_app


def _client() -> TestClient:
    return TestClient(create_app(pipeline=AsyncMock()))


class TestRequestIDMiddleware:
    def test_generates_request_id_when_absent(self):
        resp = _client().get("/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_echoes_incoming_request_id(self):
        resp = _client().get("/health", headers={"X-Request-ID": "custom-id-123"})
        assert resp.headers["X-Request-ID"] == "custom-id-123"

    def test_different_requests_get_different_ids(self):
        client = _client()
        id1 = client.get("/health").headers["X-Request-ID"]
        id2 = client.get("/health").headers["X-Request-ID"]
        assert id1 != id2

    def test_request_id_present_on_all_routes(self):
        client = _client()
        for path in ["/health", "/ready"]:
            resp = client.get(path)
            assert "X-Request-ID" in resp.headers


class TestLoggingMiddleware:
    def test_request_completes_without_error(self):
        resp = _client().get("/health")
        assert resp.status_code == 200

    def test_post_request_completes(self):
        from rag.api.dependencies import get_pipeline
        from rag.augmentation.protocols import Citation
        from rag.core.schemas import CitationMode
        from rag.pipeline.result import RAGResult
        from rag.generation.protocols import GeneratedAnswer

        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value=RAGResult(
            query_id="q", query="q", answer="a", citations=[],
            retrieval_results=[], chunks_retrieved=0, chunks_used=0,
            tokens_in=0, tokens_out=0, cached=False,
            provider="p", model="m", latency_ms=0.0, citations_used=[],
        ))

        app = create_app(pipeline=pipeline)
        app.dependency_overrides[get_pipeline] = lambda: pipeline
        client = TestClient(app)
        resp = client.post(
            "/v1/query",
            json={"query": "test", "user_id": "u", "roles": ["employee"]},
        )
        assert resp.status_code == 200


class TestAppFactory:
    def test_create_app_returns_fastapi_instance(self):
        from fastapi import FastAPI
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_openapi_schema_available(self):
        resp = _client().get("/openapi.json")
        assert resp.status_code == 200

    def test_docs_available(self):
        resp = _client().get("/docs")
        assert resp.status_code == 200

    def test_cors_headers_present_when_configured(self):
        app = create_app(pipeline=AsyncMock(), cors_origins=["https://lbg.com"])
        client = TestClient(app)
        resp = client.get("/health", headers={"Origin": "https://lbg.com"})
        assert resp.status_code == 200
