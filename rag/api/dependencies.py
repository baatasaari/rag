"""
FastAPI dependency providers.

The RAGPipeline is a singleton held in application state (app.state.pipeline).
All route handlers receive it via Depends(get_pipeline) so unit tests can
override the dependency with a mock.

Auth contract:
  The upstream API gateway (Apigee / Kong) validates the JWT and injects:
    X-User-ID:    <sub claim>
    X-User-Roles: <comma-separated roles>
  The API layer trusts these headers — it does NOT re-validate the JWT.
  Never allow unauthenticated calls through the gateway.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from rag.pipeline.orchestrator import RAGPipeline


def get_pipeline(request: Request) -> RAGPipeline:
    """Return the RAGPipeline singleton from app state."""
    pipeline: RAGPipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise RuntimeError("RAGPipeline not initialised in app.state.pipeline")
    return pipeline


PipelineDep = Annotated[RAGPipeline, Depends(get_pipeline)]


def get_request_id(
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> str | None:
    return x_request_id


RequestIDDep = Annotated[str | None, Depends(get_request_id)]
