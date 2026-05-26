"""
Tests for rag.security.audit — event schema, backends, immutability, invariants.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rag.core.exceptions import AuditLogError
from rag.core.schemas import DataClassificationLevel, SecurityConfig
from rag.security.audit import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    current_trace_id,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_security_config(
    *,
    enabled: bool = True,
    immutable: bool = True,
    wal_archive_bucket: str | None = None,
    table_name: str = "audit_events",
) -> SecurityConfig:
    cfg = MagicMock()
    cfg.audit_log.enabled = enabled
    cfg.audit_log.immutable = immutable
    cfg.audit_log.wal_archive_bucket = wal_archive_bucket
    cfg.audit_log.table_name = table_name
    return cfg


def _make_event(**overrides) -> AuditEvent:
    defaults = dict(
        event_type=AuditEventType.QUERY,
        user_id_hash="abc123" * 3,
        outcome="SUCCESS",
        session_id="sess-001",
        trace_id="0" * 32,
        rag_pattern="adaptive",
        latency_ms=150.0,
    )
    defaults.update(overrides)
    return AuditEvent(**defaults)


def _local_logger(tmp_path: Path) -> AuditLogger:
    cfg = _make_security_config(enabled=True, wal_archive_bucket=None)
    return AuditLogger(cfg, _local_path=tmp_path / "audit.jsonl")


# ── AuditEvent schema ─────────────────────────────────────────────────────────


class TestAuditEventSchema:
    def test_event_id_is_valid_uuid(self):
        event = _make_event()
        uuid.UUID(event.event_id)  # must not raise

    def test_event_id_is_unique_per_instance(self):
        e1 = _make_event()
        e2 = _make_event()
        assert e1.event_id != e2.event_id

    def test_timestamp_is_utc_iso_string(self):
        from datetime import datetime, timezone

        event = _make_event()
        dt = datetime.fromisoformat(event.timestamp)
        assert dt.tzinfo is not None

    def test_to_dict_includes_all_required_fields(self):
        event = _make_event()
        d = event.to_dict()
        required = {
            "event_id", "timestamp", "event_type", "user_id_hash",
            "outcome", "session_id", "trace_id", "rag_pattern",
            "classification_level", "pii_types_detected", "docs_accessed",
            "latency_ms",
        }
        assert required.issubset(d.keys())

    def test_to_dict_event_type_is_string_not_enum(self):
        event = _make_event()
        d = event.to_dict()
        assert isinstance(d["event_type"], str)
        assert d["event_type"] == "QUERY"

    def test_to_dict_classification_level_is_string(self):
        event = _make_event(classification_level=DataClassificationLevel.CONFIDENTIAL)
        d = event.to_dict()
        assert isinstance(d["classification_level"], str)

    def test_to_dict_is_json_serialisable(self):
        event = _make_event()
        json.dumps(event.to_dict())  # must not raise

    def test_raw_user_id_should_not_be_stored(self):
        """user_id_hash must be a hash, not a raw identifier.
        We cannot enforce the hash algorithmically here — test that
        the field name itself is user_id_hash, not user_id.
        """
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(AuditEvent)}
        assert "user_id_hash" in field_names
        assert "user_id" not in field_names

    def test_pii_types_field_is_list_not_values(self):
        """PII types list should contain type names (strings), never actual PII values."""
        event = _make_event(
            pii_types_detected=["EMAIL_ADDRESS", "NATIONAL_INSURANCE_NUMBER"]
        )
        d = event.to_dict()
        for entry in d["pii_types_detected"]:
            assert isinstance(entry, str)
            # Type names are uppercase — real values like email addresses contain @
            assert "@" not in entry

    def test_docs_accessed_is_list_of_ids_not_content(self):
        event = _make_event(docs_accessed=["doc-001", "doc-002"])
        d = event.to_dict()
        assert d["docs_accessed"] == ["doc-001", "doc-002"]

    def test_failure_event_can_carry_error_info(self):
        event = _make_event(
            outcome="FAILURE",
            error_type="EmbeddingError",
            error_component="embedding",
        )
        d = event.to_dict()
        assert d["error_type"] == "EmbeddingError"
        assert d["error_component"] == "embedding"


# ── AuditEventType enum ───────────────────────────────────────────────────────


class TestAuditEventType:
    def test_all_required_event_types_exist(self):
        required = {
            "QUERY", "RETRIEVAL", "GENERATION", "INGESTION",
            "ACCESS_DENIED", "PII_DETECTED", "CONFIG_CHANGE",
        }
        existing = {e.value for e in AuditEventType}
        assert required.issubset(existing)


# ── Local file backend ────────────────────────────────────────────────────────


class TestLocalFileBackend:
    @pytest.mark.asyncio
    async def test_event_written_to_file(self, tmp_path):
        logger = _local_logger(tmp_path)
        event = _make_event()
        await logger.log_event(event)
        lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event_id"] == event.event_id

    @pytest.mark.asyncio
    async def test_multiple_events_appended_not_overwritten(self, tmp_path):
        logger = _local_logger(tmp_path)
        for i in range(3):
            await logger.log_event(_make_event(session_id=f"sess-{i}"))
        lines = (tmp_path / "audit.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_each_line_is_valid_json(self, tmp_path):
        logger = _local_logger(tmp_path)
        await logger.log_event(_make_event())
        for line in (tmp_path / "audit.jsonl").read_text().strip().split("\n"):
            json.loads(line)  # must not raise

    @pytest.mark.asyncio
    async def test_write_failure_raises_audit_log_error(self, tmp_path):
        logger = _local_logger(tmp_path)
        # Point to a path that cannot be written (a directory)
        logger._local_path = tmp_path  # tmp_path itself is a dir, not a file
        with pytest.raises(AuditLogError) as exc_info:
            await logger.log_event(_make_event())
        assert exc_info.value.backend == "local_file"

    def test_sync_write_also_works(self, tmp_path):
        logger = _local_logger(tmp_path)
        event = _make_event()
        logger.log_event_sync(event)
        content = (tmp_path / "audit.jsonl").read_text()
        assert event.event_id in content


# ── Disabled mode ─────────────────────────────────────────────────────────────


class TestDisabledMode:
    @pytest.mark.asyncio
    async def test_disabled_does_not_write(self, tmp_path):
        cfg = _make_security_config(enabled=False)
        path = tmp_path / "audit.jsonl"
        logger = AuditLogger(cfg, _local_path=path)
        await logger.log_event(_make_event())
        assert not path.exists()

    def test_sync_disabled_does_not_write(self, tmp_path):
        cfg = _make_security_config(enabled=False)
        path = tmp_path / "audit.jsonl"
        logger = AuditLogger(cfg, _local_path=path)
        logger.log_event_sync(_make_event())
        assert not path.exists()


# ── Cloud Logging backend ─────────────────────────────────────────────────────


class TestCloudLoggingBackend:
    @pytest.mark.asyncio
    async def test_cloud_logger_log_struct_called(self, tmp_path):
        mock_cloud_logger = MagicMock()
        cfg = _make_security_config(enabled=True, wal_archive_bucket="my-bucket")
        logger = AuditLogger(cfg, _cloud_logger=mock_cloud_logger)
        event = _make_event()
        await logger.log_event(event)
        mock_cloud_logger.log_struct.assert_called_once()

    @pytest.mark.asyncio
    async def test_immutable_true_passes_insert_id(self, tmp_path):
        mock_cloud_logger = MagicMock()
        cfg = _make_security_config(enabled=True, immutable=True, wal_archive_bucket="bucket")
        logger = AuditLogger(cfg, _cloud_logger=mock_cloud_logger)
        event = _make_event()
        await logger.log_event(event)
        _, kwargs = mock_cloud_logger.log_struct.call_args
        assert kwargs.get("insert_id") == event.event_id

    @pytest.mark.asyncio
    async def test_immutable_false_does_not_set_insert_id(self, tmp_path):
        mock_cloud_logger = MagicMock()
        cfg = _make_security_config(enabled=True, immutable=False, wal_archive_bucket="bucket")
        logger = AuditLogger(cfg, _cloud_logger=mock_cloud_logger)
        await logger.log_event(_make_event())
        _, kwargs = mock_cloud_logger.log_struct.call_args
        assert kwargs.get("insert_id") is None

    @pytest.mark.asyncio
    async def test_cloud_write_failure_raises_audit_log_error(self):
        mock_cloud_logger = MagicMock()
        mock_cloud_logger.log_struct.side_effect = RuntimeError("Cloud unavailable")
        cfg = _make_security_config(enabled=True, wal_archive_bucket="bucket")
        logger = AuditLogger(cfg, _cloud_logger=mock_cloud_logger)
        with pytest.raises(AuditLogError) as exc_info:
            await logger.log_event(_make_event())
        assert exc_info.value.backend == "cloud_logging"


# ── AuditLogError ─────────────────────────────────────────────────────────────


class TestAuditLogError:
    def test_carries_backend_and_event_id(self):
        err = AuditLogError("write failed", backend="local_file", event_id="evt-123")
        assert err.backend == "local_file"
        assert err.event_id == "evt-123"

    def test_component_is_audit(self):
        err = AuditLogError("failed", backend="cloud_logging")
        assert err.component == "audit"

    def test_is_json_serialisable(self):
        err = AuditLogError("failed", backend="local_file", event_id="x")
        json.dumps(err.to_dict())


# ── current_trace_id helper ───────────────────────────────────────────────────


class TestCurrentTraceId:
    def test_returns_empty_string_when_no_active_span(self):
        trace_id = current_trace_id()
        assert isinstance(trace_id, str)
        # Without an active span, the span context is not valid → empty
        assert trace_id == "" or len(trace_id) == 32

    def test_returns_32_char_hex_when_span_active(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")

        with tracer.start_as_current_span("test-span"):
            trace_id = current_trace_id()

        assert len(trace_id) == 32
        int(trace_id, 16)  # must be valid hex
