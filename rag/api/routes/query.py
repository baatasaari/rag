"""
Query routes — POST /v1/query and GET /v1/query/stream.

POST /v1/query:
  Executes the full RAG pipeline synchronously and returns a QueryResponse.
  Suitable for request-response clients that wait for the complete answer.

GET /v1/query/stream:
  Executes retrieval and augmentation synchronously, then streams the LLM
  response as Server-Sent Events (SSE).  Each event is:
      data: <token text>\n\n
  The final event carries the sentinel:
      data: [DONE]\n\n

RBAC:
  roles from QueryRequest.roles are converted to a frozenset and passed to
  RAGPipeline.query() / stream_query() as QueryContext.allowed_roles.
  The vector store's server-side filter enforces access control.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from rag.api.dependencies import PipelineDep, RequestIDDep
from rag.api.schemas import CitationResponse, ErrorResponse, QueryRequest, QueryResponse
from rag.observability.logging import get_logger
from rag.pipeline.context import QueryContext

log = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["query"])


def _build_context(req: QueryRequest, request_id: str | None) -> QueryContext:
    return QueryContext(
        query=req.query,
        user_id=req.user_id,
        allowed_roles=frozenset(req.roles),
        session_id=req.session_id,
        filters=req.filters,
        top_k=req.top_k,
    )


def _format_citations(result) -> list[CitationResponse]:
    return [
        CitationResponse(
            index=c.index,
            title=c.title,
            source_uri=c.source_uri,
            page=c.page,
        )
        for c in result.citations
    ]


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Execute a RAG query",
    responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def query(
    req: QueryRequest,
    pipeline: PipelineDep,
    request: Request,
    request_id: RequestIDDep,
) -> QueryResponse:
    ctx = _build_context(req, request_id)
    log.info("api.query.start", query_id=ctx.query_id, user_id=req.user_id)
    try:
        result = await pipeline.query(ctx)
    except Exception as exc:
        log.error("api.query.error", error=str(exc), query_id=ctx.query_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return QueryResponse(
        query_id=result.query_id,
        answer=result.answer,
        citations=_format_citations(result),
        cached=result.cached,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        model=result.model,
        provider=result.provider,
        chunks_retrieved=result.chunks_retrieved,
        chunks_used=result.chunks_used,
    )


@router.post(
    "/query/stream",
    summary="Stream a RAG query response via SSE",
    response_class=StreamingResponse,
)
async def query_stream(
    req: QueryRequest,
    pipeline: PipelineDep,
    request: Request,
    request_id: RequestIDDep,
) -> StreamingResponse:
    ctx = _build_context(req, request_id)
    log.info("api.query_stream.start", query_id=ctx.query_id, user_id=req.user_id)

    async def _sse_generator() -> AsyncIterator[str]:
        try:
            async for token in pipeline.stream_query(ctx):
                # SSE format: "data: <payload>\n\n"
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            log.error("api.query_stream.error", error=str(exc), query_id=ctx.query_id)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
