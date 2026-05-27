"""
API Pydantic schemas — request and response models for all endpoints.

Validation rules:
  - query must be 1–2000 chars (prevent prompt injection via oversized inputs)
  - roles must be a non-empty list (at least one RBAC role is always required)
  - top_k, if provided, must be between 1 and 200

FCA / data-handling:
  - CitationResponse never exposes chunk_id or allowed_roles metadata —
    only the source_uri, title, and page needed for attribution.
  - ErrorResponse never echoes the raw query back (audit logs capture it
    via structlog, not HTTP responses).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Shared primitives ─────────────────────────────────────────────────────────


class CitationResponse(BaseModel):
    index: int
    title: str
    source_uri: str
    page: int | None = None


class ErrorResponse(BaseModel):
    error: str
    code: str
    request_id: str | None = None


# ── Query ─────────────────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="User query string.")
    user_id: str = Field(..., min_length=1, description="Authenticated user identifier.")
    roles: list[str] = Field(
        ...,
        min_length=1,
        description="RBAC roles from the upstream auth gateway.",
    )
    session_id: str | None = Field(default=None, description="Conversation session ID.")
    filters: dict[str, Any] | None = Field(
        default=None, description="Server-side metadata filters."
    )
    top_k: int | None = Field(
        default=None, ge=1, le=200,
        description="Override retrieval.top_k for this request.",
    )

    @field_validator("roles")
    @classmethod
    def roles_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("roles must contain at least one entry.")
        return v

    @field_validator("query")
    @classmethod
    def query_stripped(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be blank after stripping whitespace.")
        return stripped


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    citations: list[CitationResponse]
    cached: bool
    tokens_in: int
    tokens_out: int
    latency_ms: float
    model: str
    provider: str
    chunks_retrieved: int
    chunks_used: int


# ── Ingest ────────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    source_uri: str = Field(
        ...,
        min_length=1,
        description="URI of the document to ingest (GCS, SharePoint, Confluence, etc.).",
    )
    doc_type: str = Field(default="auto", description="Document type hint.")
    metadata: dict[str, Any] = Field(default_factory=dict)
    roles: list[str] = Field(
        default_factory=list,
        description="RBAC roles that may access this document.",
    )


class IngestResponse(BaseModel):
    doc_id: str
    chunks_created: int
    status: str


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str   # "ok" | "degraded"
    version: str
    checks: dict[str, bool]


class ReadyResponse(BaseModel):
    ready: bool
    details: dict[str, str] = Field(default_factory=dict)
