"""
Ingest route — POST /v1/ingest.

Accepts a document URI and triggers the ingestion pipeline.  Returns a
doc_id and chunk count once ingestion completes.

The ingestion pipeline (rag.ingestion.pipeline.IngestionPipeline) must be
stored in app.state.ingestion_pipeline.  If it is absent the endpoint returns
503 Service Unavailable so the service can start in query-only mode.

Access control:
  Only users with the "ingest" role may call this endpoint.
  Role enforcement is done here (not in the ingestion pipeline) so that
  the pipeline remains role-agnostic for batch jobs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from rag.api.dependencies import RequestIDDep
from rag.api.schemas import ErrorResponse, IngestRequest, IngestResponse
from rag.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["ingest"])

_INGEST_ROLE = "ingest"


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest a document into the RAG knowledge base",
    responses={
        403: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def ingest(
    req: IngestRequest,
    request: Request,
    request_id: RequestIDDep,
) -> IngestResponse:
    # Require the "ingest" role
    caller_roles: list[str] = req.roles
    if _INGEST_ROLE not in caller_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{_INGEST_ROLE}' required to ingest documents.",
        )

    ingestion_pipeline = getattr(request.app.state, "ingestion_pipeline", None)
    if ingestion_pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion pipeline is not available.",
        )

    log.info("api.ingest.start", source_uri=req.source_uri, doc_type=req.doc_type)
    try:
        result = await ingestion_pipeline.run(
            source_uri=req.source_uri,
            doc_type=req.doc_type,
            metadata=req.metadata,
            allowed_roles=frozenset(req.roles),
        )
    except Exception as exc:
        log.error("api.ingest.error", error=str(exc), source_uri=req.source_uri)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    log.info(
        "api.ingest.complete",
        doc_id=result.doc_id,
        chunks_created=result.chunks_created,
    )
    return IngestResponse(
        doc_id=result.doc_id,
        chunks_created=result.chunks_created,
        status="ok",
    )
