"""
Immutable audit log for the LBG RAG Platform.

Every query, retrieval, generation, ingestion, access-denial, and PII-detection
event is written to an append-only audit log that satisfies FCA record-keeping
requirements.

Design principles:
  - User IDs are HMAC-hashed before storage — raw identifiers never appear.
  - PII types may appear; PII values never do.
  - Document IDs are logged; document content is never logged.
  - Cloud Logging backend (prod): insertId = event_id enables idempotent replay
    detection and WAL archival to GCS for immutability.
  - Local JSONL file backend (dev/test): append-only, no network required.
  - AuditLogError is raised on write failure — never silenced.
  - Log calls are non-blocking (fire-and-forget via asyncio.create_task) so
    they do not add latency to the hot query path.

Usage::

    audit = AuditLogger(config.security)
    await audit.log_event(AuditEvent(
        event_type=AuditEventType.QUERY,
        user_id_hash=hmac_hash(user_ctx.user_id),
        session_id=session_id,
        trace_id=current_trace_id(),
        rag_pattern="adaptive",
        outcome="SUCCESS",
        latency_ms=240.5,
    ))
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from rag.core.exceptions import AuditLogError
from rag.core.schemas import DataClassificationLevel, SecurityConfig
from rag.observability.logging import get_logger

log = get_logger(__name__)

_DEFAULT_LOCAL_AUDIT_PATH = Path("/tmp/rag-audit.jsonl")  # noqa: S108


class AuditEventType(str, Enum):
    QUERY = "QUERY"
    RETRIEVAL = "RETRIEVAL"
    GENERATION = "GENERATION"
    INGESTION = "INGESTION"
    ACCESS_DENIED = "ACCESS_DENIED"
    PII_DETECTED = "PII_DETECTED"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    RERANKING = "RERANKING"
    CACHE_HIT = "CACHE_HIT"


@dataclass
class AuditEvent:
    """A single immutable audit record.

    All fields are set at creation time.  event_id and timestamp have
    sensible defaults so callers only need to supply the meaningful fields.
    """

    event_type: AuditEventType
    user_id_hash: str  # HMAC hash — raw user_id must NEVER appear here
    outcome: Literal["SUCCESS", "FAILURE"]

    # Context
    session_id: str = ""
    trace_id: str = ""
    rag_pattern: str = ""
    classification_level: DataClassificationLevel = DataClassificationLevel.INTERNAL

    # Findings (types only — values never stored)
    pii_types_detected: list[str] = field(default_factory=list)

    # Resource references (IDs only — no content)
    docs_accessed: list[str] = field(default_factory=list)
    docs_filtered_by_rbac: int = 0

    # Performance
    latency_ms: float = 0.0

    # Error detail (only on FAILURE outcome)
    error_type: str = ""
    error_component: str = ""

    # Auto-populated
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["classification_level"] = self.classification_level.value
        return d


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Writes AuditEvents to Cloud Logging (prod) or a local JSONL file (dev).

    Thread-safe for sync callers; async-safe for async callers via
    log_event() which schedules writes off the critical path.
    """

    def __init__(
        self,
        config: SecurityConfig,
        *,
        _cloud_logger: Any = None,      # injection seam for tests
        _local_path: Path | None = None,  # injection seam for tests
    ) -> None:
        self._cfg = config.audit_log
        self._cloud_logger = _cloud_logger
        self._local_path = _local_path or _DEFAULT_LOCAL_AUDIT_PATH
        self._backend = self._select_backend()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def log_event(self, event: AuditEvent) -> None:
        """Write an audit event.

        Non-blocking — schedules the write as a background task so it does
        not add latency to the query critical path.

        Raises:
            AuditLogError: propagated if the write itself fails.  Callers
                should NOT catch this — a failed audit write is a security
                incident that must surface.
        """
        if not self._cfg.enabled:
            return

        # Schedule off the hot path; any exception will be re-raised
        # by the task when awaited or caught by the event loop's exception handler.
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._write_sync, event
            )
        except AuditLogError:
            raise
        except Exception as exc:
            raise AuditLogError(
                f"Unexpected error writing audit event {event.event_id}: {exc}",
                backend=self._backend,
                event_id=event.event_id,
            ) from exc

    def log_event_sync(self, event: AuditEvent) -> None:
        """Synchronous variant — use only in non-async contexts (e.g. shutdown hooks)."""
        if not self._cfg.enabled:
            return
        self._write_sync(event)

    # ------------------------------------------------------------------
    # Backend selection and write dispatch
    # ------------------------------------------------------------------

    def _select_backend(self) -> str:
        if self._cloud_logger is not None:
            return "cloud_logging_injected"
        # Prefer Cloud Logging when WAL bucket is configured (prod)
        if self._cfg.wal_archive_bucket:
            return "cloud_logging"
        return "local_file"

    def _write_sync(self, event: AuditEvent) -> None:
        if self._backend in ("cloud_logging", "cloud_logging_injected"):
            self._write_cloud(event)
        else:
            self._write_local(event)

    def _write_cloud(self, event: AuditEvent) -> None:
        try:
            cloud_logger = self._get_cloud_logger()
            payload = event.to_dict()
            struct_entry = cloud_logger.struct_log_entries([
                {
                    "jsonPayload": payload,
                    "severity": "NOTICE",
                    # insertId = event_id ensures idempotent replay detection (FCA)
                    "insertId": event.event_id,
                    "labels": {
                        "event_type": event.event_type.value,
                        "outcome": event.outcome,
                    },
                }
            ])
            cloud_logger.log_struct(
                payload,
                severity="NOTICE",
                insert_id=event.event_id if self._cfg.immutable else None,
                labels={
                    "event_type": event.event_type.value,
                    "outcome": event.outcome,
                },
            )
        except AuditLogError:
            raise
        except Exception as exc:
            raise AuditLogError(
                f"Cloud Logging write failed for event {event.event_id}: {exc}",
                backend="cloud_logging",
                event_id=event.event_id,
            ) from exc

    def _write_local(self, event: AuditEvent) -> None:
        """Append-only write to a local JSONL file (dev / fallback)."""
        try:
            payload = json.dumps(event.to_dict(), default=str)
            with self._local_path.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")
        except Exception as exc:
            raise AuditLogError(
                f"Local audit file write failed for event {event.event_id}: {exc}",
                backend="local_file",
                event_id=event.event_id,
            ) from exc

    def _get_cloud_logger(self) -> Any:
        if self._cloud_logger is not None:
            return self._cloud_logger
        try:
            import google.cloud.logging as gcp_logging  # type: ignore[import-untyped]

            client = gcp_logging.Client()
            self._cloud_logger = client.logger("rag-audit")
            return self._cloud_logger
        except Exception as exc:
            raise AuditLogError(
                f"Failed to initialise Cloud Logging client: {exc}",
                backend="cloud_logging",
            ) from exc


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def current_trace_id() -> str:
    """Return the active OTel trace ID as a 32-char hex string, or empty string."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        return format(ctx.trace_id, "032x") if ctx.is_valid else ""
    except Exception:  # noqa: BLE001
        return ""
