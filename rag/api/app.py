"""
FastAPI application factory.

Usage:
    # In uvicorn entrypoint:
    from rag.api.app import create_app
    app = create_app()

    # Or via CLI:
    uvicorn rag.api.app:create_app --factory --host 0.0.0.0 --port 8080

Lifespan:
  The lifespan context manager is the hook for wiring the RAGPipeline
  singleton.  In production, create_app() accepts optional pre-built
  pipeline / ingestion_pipeline objects; when absent, the app starts in
  degraded mode (health endpoint returns 503 until injected).

OpenTelemetry:
  FastAPIInstrumentor patches the app automatically if the opentelemetry-
  instrumentation-fastapi package is installed.  Spans are exported to the
  configured OTLP endpoint via the tracing module.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag.api.middleware import LoggingMiddleware, RequestIDMiddleware
from rag.api.routes import health as health_router
from rag.api.routes import ingest as ingest_router
from rag.api.routes import query as query_router
from rag.api.schemas import ErrorResponse
from rag.observability.logging import get_logger
from rag.pipeline.orchestrator import RAGPipeline

log = get_logger(__name__)

_TITLE = "LBG RAG Platform"
_DESCRIPTION = "Enterprise Retrieval-Augmented Generation API for Lloyds Banking Group."
_VERSION = "1.0.0"


def create_app(
    *,
    pipeline: RAGPipeline | None = None,
    ingestion_pipeline=None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        pipeline:           Pre-built RAGPipeline.  If None the app starts in
                            degraded mode; inject via app.state.pipeline later.
        ingestion_pipeline: Pre-built IngestionPipeline.  Optional.
        cors_origins:       CORS allowed origins.  Defaults to deny-all.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.pipeline = pipeline
        app.state.ingestion_pipeline = ingestion_pipeline
        log.info(
            "api.startup",
            pipeline_ready=pipeline is not None,
            ingestion_ready=ingestion_pipeline is not None,
        )
        yield
        log.info("api.shutdown")

    app = FastAPI(
        title=_TITLE,
        description=_DESCRIPTION,
        version=_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware (outermost = last added) ───────────────────────────────────
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or [],
        allow_credentials=True,
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router.router)
    app.include_router(query_router.router)
    app.include_router(ingest_router.router)

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        log.error("api.unhandled_exception", error=str(exc), request_id=request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="An unexpected error occurred.",
                code="INTERNAL_ERROR",
                request_id=request_id,
            ).model_dump(),
        )

    # ── OpenTelemetry instrumentation (lazy) ──────────────────────────────────
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # type: ignore[import]
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass

    return app
