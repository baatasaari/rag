"""
LBG RAG — REST API Layer

Public surface:
  create_app   — FastAPI application factory (called by uvicorn entrypoint)

Internal structure:
  schemas.py       — Pydantic request/response models
  dependencies.py  — FastAPI dependency providers (pipeline, auth)
  middleware.py     — Request-ID injection, RBAC header extraction
  routes/query.py  — POST /v1/query, GET /v1/query/stream (SSE)
  routes/ingest.py — POST /v1/ingest
  routes/health.py — GET /health, GET /ready
  app.py           — Application factory and lifespan
"""

from rag.api.app import create_app

__all__ = ["create_app"]
