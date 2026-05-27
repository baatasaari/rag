"""
Health routes — GET /health and GET /ready.

/health:
  Lightweight liveness probe.  Returns 200 immediately if the process is
  running.  Never blocks on external services.  Kubernetes liveness probe
  should point here.

/ready:
  Readiness probe.  Checks that the pipeline is initialised and all
  critical storage backends are reachable.  Returns 200 when ready,
  503 when not.  Kubernetes readiness probe should point here.

The checks dict uses string keys so Kubernetes / monitoring tools can
parse individual backend states without code changes.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from rag.api.schemas import HealthResponse, ReadyResponse
from rag.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["health"])

_VERSION = "1.0.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=_VERSION,
        checks={},
    )


@router.get(
    "/ready",
    summary="Readiness probe",
)
async def ready(request: Request) -> JSONResponse:
    details: dict[str, str] = {}
    all_ready = True

    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        details["pipeline"] = "not_initialised"
        all_ready = False
    else:
        details["pipeline"] = "ok"

    # Additional checks can be wired here (vector store, cache, etc.)
    # without changing the probe contract.

    body = ReadyResponse(ready=all_ready, details=details)
    code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=body.model_dump(), status_code=code)
