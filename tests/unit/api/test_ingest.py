"""
Tests for rag.api.routes.ingest — POST /v1/ingest.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from rag.api.app import create_app


def _ingest_result(doc_id: str = "doc-abc", chunks: int = 12):
    r = MagicMock()
    r.doc_id = doc_id
    r.chunks_created = chunks
    return r


def _client(ingestion_pipeline=None, pipeline=None) -> TestClient:
    app = create_app(pipeline=pipeline or AsyncMock(), ingestion_pipeline=ingestion_pipeline)
    app.state.ingestion_pipeline = ingestion_pipeline
    app.state.pipeline = pipeline or AsyncMock()
    return TestClient(app)


_INGEST_BODY = {
    "source_uri": "gs://lbg-docs/policy.pdf",
    "roles": ["ingest", "employee"],
}


class TestIngestEndpoint:
    def test_returns_200_when_authorised(self):
        ingest_pipe = AsyncMock()
        ingest_pipe.run = AsyncMock(return_value=_ingest_result())
        resp = _client(ingestion_pipeline=ingest_pipe).post("/v1/ingest", json=_INGEST_BODY)
        assert resp.status_code == 200

    def test_response_schema(self):
        ingest_pipe = AsyncMock()
        ingest_pipe.run = AsyncMock(return_value=_ingest_result("doc-xyz", 7))
        resp = _client(ingestion_pipeline=ingest_pipe).post("/v1/ingest", json=_INGEST_BODY)
        body = resp.json()
        assert body["doc_id"] == "doc-xyz"
        assert body["chunks_created"] == 7
        assert body["status"] == "ok"

    def test_missing_ingest_role_returns_403(self):
        ingest_pipe = AsyncMock()
        body = {**_INGEST_BODY, "roles": ["employee"]}  # no "ingest" role
        resp = _client(ingestion_pipeline=ingest_pipe).post("/v1/ingest", json=body)
        assert resp.status_code == 403

    def test_no_ingestion_pipeline_returns_503(self):
        resp = _client(ingestion_pipeline=None).post("/v1/ingest", json=_INGEST_BODY)
        assert resp.status_code == 503

    def test_ingestion_error_returns_500(self):
        ingest_pipe = AsyncMock()
        ingest_pipe.run = AsyncMock(side_effect=RuntimeError("DB connection failed"))
        app = create_app(pipeline=AsyncMock(), ingestion_pipeline=ingest_pipe)
        app.state.ingestion_pipeline = ingest_pipe
        app.state.pipeline = AsyncMock()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/v1/ingest", json=_INGEST_BODY)
        assert resp.status_code == 500

    def test_empty_source_uri_returns_422(self):
        ingest_pipe = AsyncMock()
        body = {**_INGEST_BODY, "source_uri": ""}
        resp = _client(ingestion_pipeline=ingest_pipe).post("/v1/ingest", json=body)
        assert resp.status_code == 422

    def test_metadata_forwarded(self):
        ingest_pipe = AsyncMock()
        ingest_pipe.run = AsyncMock(return_value=_ingest_result())
        body = {**_INGEST_BODY, "metadata": {"region": "UK"}}
        _client(ingestion_pipeline=ingest_pipe).post("/v1/ingest", json=body)
        _, kwargs = ingest_pipe.run.call_args
        assert kwargs["metadata"] == {"region": "UK"}

    def test_roles_converted_to_frozenset(self):
        ingest_pipe = AsyncMock()
        ingest_pipe.run = AsyncMock(return_value=_ingest_result())
        _client(ingestion_pipeline=ingest_pipe).post("/v1/ingest", json=_INGEST_BODY)
        _, kwargs = ingest_pipe.run.call_args
        assert isinstance(kwargs["allowed_roles"], frozenset)
        assert "employee" in kwargs["allowed_roles"]
