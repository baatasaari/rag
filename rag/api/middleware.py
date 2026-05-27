"""
API middleware.

RequestIDMiddleware:
  Ensures every response carries an X-Request-ID header.  If the incoming
  request provides one, it is echo'd back.  Otherwise a new UUID is generated.
  The request_id is stored in request.state so route handlers can include it
  in error responses.

LoggingMiddleware:
  Emits a structured log entry on every request: method, path, status code,
  latency, and request_id.  Does NOT log query text (PII risk).
"""

from __future__ import annotations

import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from rag.observability.logging import get_logger

log = get_logger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request_id to every request and echo it in the response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status, and latency."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        t0 = time.monotonic()
        response = await call_next(request)
        latency_ms = round((time.monotonic() - t0) * 1000)
        request_id = getattr(request.state, "request_id", None)
        log.info(
            "api.request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        return response
