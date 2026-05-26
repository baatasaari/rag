"""
Tests for rag.security.pii — PII detection, redaction, modes, and invariants.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag.core.exceptions import PIIDetectedError
from rag.core.schemas import PIIAction, SecurityConfig
from rag.security.pii import (
    PIIDetectionResult,
    PIIDetector,
    PIIFinding,
    UK_INFO_TYPES,
    _REDACTION_ACTIONS,
    _parse_findings,
    _parse_transformation_summary,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_security_config(
    *,
    enabled: bool = True,
    project_id: str = "test-project",
    log_finding_types: bool = True,
) -> SecurityConfig:
    cfg = MagicMock()
    cfg.pii_detection.enabled = enabled
    cfg.pii_detection.project_id = project_id
    cfg.pii_detection.log_finding_types = log_finding_types
    cfg.pii_detection.provider = "cloud_dlp"
    cfg.pii_detection.emit_audit_event = False
    return cfg


def _make_dlp_inspect_response(findings: list[tuple[str, int]]) -> MagicMock:
    """Build a mock DLP inspect_content response with given (type, count) pairs."""
    mock_findings = []
    for info_type_name, count in findings:
        for _ in range(count):
            f = MagicMock()
            f.info_type.name = info_type_name
            mock_findings.append(f)
    response = MagicMock()
    response.result.findings = mock_findings
    return response


def _make_dlp_deidentify_response(
    original: str,
    redacted: str,
    summaries: list[tuple[str, int]],
) -> MagicMock:
    """Build a mock DLP deidentify_content response."""
    mock_summaries = []
    for type_name, count in summaries:
        s = MagicMock()
        s.info_type.name = type_name
        s.transformed_bytes = count * 10  # non-zero = something was transformed
        s.transformation_count = count
        mock_summaries.append(s)
    response = MagicMock()
    response.item.value = redacted
    response.overview.transformation_summaries = mock_summaries
    return response


def _make_detector(
    *,
    enabled: bool = True,
    inspect_response: MagicMock | None = None,
    deidentify_response: MagicMock | None = None,
) -> PIIDetector:
    cfg = _make_security_config(enabled=enabled)
    mock_client = MagicMock()
    if inspect_response is not None:
        mock_client.inspect_content.return_value = inspect_response
    if deidentify_response is not None:
        mock_client.deidentify_content.return_value = deidentify_response
    return PIIDetector(cfg, _dlp_client=mock_client)


# ── UK_INFO_TYPES ─────────────────────────────────────────────────────────────


class TestInfoTypes:
    def test_national_insurance_number_included(self):
        assert "NATIONAL_INSURANCE_NUMBER" in UK_INFO_TYPES

    def test_uk_sort_code_included(self):
        assert "UK_SORT_CODE" in UK_INFO_TYPES

    def test_email_address_included(self):
        assert "EMAIL_ADDRESS" in UK_INFO_TYPES

    def test_no_duplicates(self):
        assert len(UK_INFO_TYPES) == len(set(UK_INFO_TYPES))


# ── PIIDetectionResult ────────────────────────────────────────────────────────


class TestPIIDetectionResult:
    def test_pii_types_property(self):
        result = PIIDetectionResult(
            clean_text="text",
            findings=[
                PIIFinding(info_type="EMAIL_ADDRESS", count=1),
                PIIFinding(info_type="PHONE_NUMBER", count=2),
            ],
        )
        assert result.pii_types == ["EMAIL_ADDRESS", "PHONE_NUMBER"]

    def test_empty_findings_pii_types_is_empty(self):
        result = PIIDetectionResult(clean_text="clean text")
        assert result.pii_types == []

    def test_findings_count_accessible(self):
        finding = PIIFinding(info_type="NATIONAL_INSURANCE_NUMBER", count=3)
        assert finding.count == 3
        assert finding.info_type == "NATIONAL_INSURANCE_NUMBER"

    def test_finding_is_frozen(self):
        finding = PIIFinding(info_type="EMAIL_ADDRESS", count=1)
        with pytest.raises((AttributeError, TypeError)):
            finding.count = 99  # type: ignore[misc]


# ── Disabled mode ─────────────────────────────────────────────────────────────


class TestDisabledMode:
    @pytest.mark.asyncio
    async def test_disabled_returns_text_unchanged(self):
        detector = _make_detector(enabled=False)
        result = await detector.scan("NI number: AB123456C", action=PIIAction.REDACT)
        assert result.clean_text == "NI number: AB123456C"
        assert result.findings == []
        assert not result.was_modified

    @pytest.mark.asyncio
    async def test_disabled_does_not_call_dlp(self):
        cfg = _make_security_config(enabled=False)
        mock_client = MagicMock()
        detector = PIIDetector(cfg, _dlp_client=mock_client)
        await detector.scan("text", action=PIIAction.REDACT)
        mock_client.inspect_content.assert_not_called()
        mock_client.deidentify_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_does_not_raise_on_empty_text(self):
        detector = _make_detector(enabled=False)
        result = await detector.scan("")
        assert result.clean_text == ""


# ── Empty / trivial inputs ────────────────────────────────────────────────────


class TestTrivialInputs:
    @pytest.mark.asyncio
    async def test_empty_string_returns_immediately(self):
        mock_client = MagicMock()
        cfg = _make_security_config(enabled=True)
        detector = PIIDetector(cfg, _dlp_client=mock_client)
        result = await detector.scan("")
        mock_client.inspect_content.assert_not_called()
        assert result.clean_text == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_returns_immediately(self):
        mock_client = MagicMock()
        cfg = _make_security_config(enabled=True)
        detector = PIIDetector(cfg, _dlp_client=mock_client)
        result = await detector.scan("   ")
        mock_client.inspect_content.assert_not_called()


# ── REDACT mode ───────────────────────────────────────────────────────────────


class TestRedactMode:
    @pytest.mark.asyncio
    async def test_redact_calls_deidentify_not_inspect(self):
        mock_client = MagicMock()
        mock_client.deidentify_content.return_value = _make_dlp_deidentify_response(
            "original", "redacted", []
        )
        cfg = _make_security_config(enabled=True)
        detector = PIIDetector(cfg, _dlp_client=mock_client)
        await detector.scan("text with PII", action=PIIAction.REDACT)
        mock_client.deidentify_content.assert_called_once()
        mock_client.inspect_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_redact_returns_clean_text(self):
        resp = _make_dlp_deidentify_response(
            "My email is alice@example.com",
            "My email is [EMAIL_ADDRESS]",
            [("EMAIL_ADDRESS", 1)],
        )
        detector = _make_detector(deidentify_response=resp)
        result = await detector.scan("My email is alice@example.com", action=PIIAction.REDACT)
        assert result.clean_text == "My email is [EMAIL_ADDRESS]"
        assert result.was_modified

    @pytest.mark.asyncio
    async def test_redact_does_not_raise_on_pii_found(self):
        resp = _make_dlp_deidentify_response(
            "NI: AB123456C",
            "NI: [NATIONAL_INSURANCE_NUMBER]",
            [("NATIONAL_INSURANCE_NUMBER", 1)],
        )
        detector = _make_detector(deidentify_response=resp)
        # Must NOT raise even though PII was found
        result = await detector.scan("NI: AB123456C", action=PIIAction.REDACT)
        assert result.findings

    @pytest.mark.asyncio
    async def test_redact_with_no_pii_returns_original(self):
        resp = _make_dlp_deidentify_response("clean text", "clean text", [])
        detector = _make_detector(deidentify_response=resp)
        result = await detector.scan("clean text", action=PIIAction.REDACT)
        assert result.clean_text == "clean text"
        assert not result.was_modified
        assert result.findings == []

    @pytest.mark.asyncio
    async def test_replace_with_info_type_uses_deidentify(self):
        resp = _make_dlp_deidentify_response("text", "text", [])
        mock_client = MagicMock()
        mock_client.deidentify_content.return_value = resp
        cfg = _make_security_config(enabled=True)
        detector = PIIDetector(cfg, _dlp_client=mock_client)
        await detector.scan("text", action=PIIAction.REPLACE_WITH_INFO_TYPE)
        mock_client.deidentify_content.assert_called_once()


# ── Non-redaction mode (inspect) ──────────────────────────────────────────────


class TestInspectMode:
    @pytest.mark.asyncio
    async def test_pseudonymize_calls_inspect_not_deidentify(self):
        resp = _make_dlp_inspect_response([])
        mock_client = MagicMock()
        mock_client.inspect_content.return_value = resp
        cfg = _make_security_config(enabled=True)
        detector = PIIDetector(cfg, _dlp_client=mock_client)
        await detector.scan("clean text", action=PIIAction.PSEUDONYMIZE)
        mock_client.inspect_content.assert_called_once()
        mock_client.deidentify_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_pii_found_in_pseudonymize_mode_raises(self):
        resp = _make_dlp_inspect_response([("EMAIL_ADDRESS", 1)])
        detector = _make_detector(inspect_response=resp)
        with pytest.raises(PIIDetectedError) as exc_info:
            await detector.scan("email@example.com", action=PIIAction.PSEUDONYMIZE)
        assert "EMAIL_ADDRESS" in exc_info.value.pii_types

    @pytest.mark.asyncio
    async def test_no_pii_in_pseudonymize_mode_no_raise(self):
        resp = _make_dlp_inspect_response([])
        detector = _make_detector(inspect_response=resp)
        result = await detector.scan("clean text", action=PIIAction.PSEUDONYMIZE)
        assert result.findings == []
        assert result.clean_text == "clean text"


# ── PIIDetectedError invariants ───────────────────────────────────────────────


class TestPIIDetectedError:
    @pytest.mark.asyncio
    async def test_error_carries_pii_types_not_values(self):
        resp = _make_dlp_inspect_response([
            ("EMAIL_ADDRESS", 1),
            ("PHONE_NUMBER", 1),
        ])
        detector = _make_detector(inspect_response=resp)
        with pytest.raises(PIIDetectedError) as exc_info:
            await detector.scan("text", action=PIIAction.PSEUDONYMIZE)
        err = exc_info.value
        assert "EMAIL_ADDRESS" in err.pii_types
        assert "PHONE_NUMBER" in err.pii_types
        # The actual email/phone value must not appear in the error message
        assert "text" not in str(err)

    @pytest.mark.asyncio
    async def test_error_is_json_serialisable(self):
        import json

        resp = _make_dlp_inspect_response([("EMAIL_ADDRESS", 1)])
        detector = _make_detector(inspect_response=resp)
        with pytest.raises(PIIDetectedError) as exc_info:
            await detector.scan("x", action=PIIAction.PSEUDONYMIZE)
        json.dumps(exc_info.value.to_dict())  # must not raise

    def test_error_component_is_security(self):
        err = PIIDetectedError(pii_types=["EMAIL_ADDRESS"])
        assert err.component == "security"


# ── _parse_findings helper ────────────────────────────────────────────────────


class TestParseFindings:
    def test_aggregates_counts_by_type(self):
        raw = []
        for _ in range(3):
            f = MagicMock()
            f.info_type.name = "EMAIL_ADDRESS"
            raw.append(f)
        f2 = MagicMock()
        f2.info_type.name = "PHONE_NUMBER"
        raw.append(f2)
        results = _parse_findings(raw)
        email = next(r for r in results if r.info_type == "EMAIL_ADDRESS")
        phone = next(r for r in results if r.info_type == "PHONE_NUMBER")
        assert email.count == 3
        assert phone.count == 1

    def test_empty_findings_returns_empty_list(self):
        assert _parse_findings([]) == []


# ── _REDACTION_ACTIONS set ────────────────────────────────────────────────────


class TestRedactionActionsSet:
    def test_redact_is_redaction_action(self):
        assert PIIAction.REDACT in _REDACTION_ACTIONS

    def test_replace_with_info_type_is_redaction_action(self):
        assert PIIAction.REPLACE_WITH_INFO_TYPE in _REDACTION_ACTIONS

    def test_pseudonymize_is_not_redaction_action(self):
        assert PIIAction.PSEUDONYMIZE not in _REDACTION_ACTIONS
