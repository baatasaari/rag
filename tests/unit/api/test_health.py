"""
Tests for rag.api.routes.health — GET /health and GET /ready.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from rag.api.app import create_app


def _client(with_pipeline: bool = True) -> TestClient:
    pipeline = AsyncMock() if with_pipeline else None
    app = create_app(pipeline=pipeline)
    # Set state directly — TestClient doesn't trigger lifespan without `with` block.
    app.state.pipeline = pipeline
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self):
        assert _client().get("/health").status_code == 200

    def test_status_ok(self):
        body = _client().get("/health").json()
        assert body["status"] == "ok"

    def test_version_present(self):
        body = _client().get("/health").json()
        assert "version" in body
        assert body["version"]

    def test_works_without_pipeline(self):
        assert _client(with_pipeline=False).get("/health").status_code == 200


class TestReadyEndpoint:
    def test_ready_with_pipeline_returns_200(self):
        assert _client(with_pipeline=True).get("/ready").status_code == 200

    def test_ready_without_pipeline_returns_503(self):
        assert _client(with_pipeline=False).get("/ready").status_code == 503

    def test_ready_body_when_ok(self):
        body = _client(with_pipeline=True).get("/ready").json()
        assert body["ready"] is True
        assert body["details"]["pipeline"] == "ok"

    def test_ready_body_when_not_ready(self):
        body = _client(with_pipeline=False).get("/ready").json()
        assert body["ready"] is False
        assert "pipeline" in body["details"]
