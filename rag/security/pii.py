"""
PII detection and de-identification for the LBG RAG Platform.

Uses Google Cloud DLP to detect UK-specific PII in text inputs (queries and
documents).  Three action modes controlled by config:

  REDACT               — replace PII with typed tokens, e.g. [EMAIL_ADDRESS]
  REPLACE_WITH_INFO_TYPE — alias for REDACT (DLP's native mode)
  PSEUDONYMIZE / MASK / ENCRYPT — extended DLP transformation modes

Critical invariants:
  - The actual PII *value* is NEVER stored, logged, or returned.
  - Only the PII *type* and *count* appear in PIIFinding.
  - OTel span and metrics counter are updated per scan.
  - When enabled=False (dev without GCP), returns the text unchanged with no findings.

Usage::

    detector = PIIDetector(config.security)
    result = await detector.scan(user_query, action=PIIAction.REDACT)
    if result.findings:
        log.info("pii.detected", types=[f.info_type for f in result.findings])
    clean_text = result.clean_text
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from rag.core.exceptions import PIIDetectedError
from rag.core.schemas import PIIAction, SecurityConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)

# UK PII info-types recognised by Cloud DLP.
UK_INFO_TYPES: list[str] = [
    "NATIONAL_INSURANCE_NUMBER",
    "UK_SORT_CODE",
    "UK_BANK_ACCOUNT_NUMBER",
    "UK_PASSPORT",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "PERSON_NAME",
    "CREDIT_CARD_NUMBER",
    "IBAN_CODE",
    "DATE_OF_BIRTH",
    "STREET_ADDRESS",
    "LOCATION",
]


@dataclass(frozen=True)
class PIIFinding:
    """A single PII type found in text.  The actual value is never stored here."""

    info_type: str
    count: int


@dataclass
class PIIDetectionResult:
    """Result of a PII scan."""

    clean_text: str
    findings: list[PIIFinding] = field(default_factory=list)
    was_modified: bool = False

    @property
    def pii_types(self) -> list[str]:
        return [f.info_type for f in self.findings]


class PIIDetector:
    """Cloud DLP-backed PII detector and de-identifier.

    Pass the full SecurityConfig (not just PIIDetectionConfig) so the detector
    can also interact with the audit log config when emit_audit_event=True.
    """

    def __init__(
        self,
        config: SecurityConfig,
        *,
        _dlp_client: Any = None,  # injection seam for tests
    ) -> None:
        self._cfg = config.pii_detection
        self._dlp_client = _dlp_client  # None → lazy-init on first real call

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scan(
        self,
        text: str,
        *,
        action: PIIAction | None = None,
    ) -> PIIDetectionResult:
        """Scan text for PII and apply the configured action.

        Args:
            text:   Text to inspect.  May be a query, chunk, or document excerpt.
            action: Override the default action from config.  Useful when callers
                    need different behaviour (e.g. REDACT for ingestion, block for
                    query inputs that must be clean).

        Returns:
            PIIDetectionResult with clean_text and findings (type + count only).

        Raises:
            PIIDetectedError: Only raised when action is not a redaction variant
                and PII is detected.  Never raised in REDACT mode.
        """
        if not text or not text.strip():
            return PIIDetectionResult(clean_text=text)

        effective_action = action or PIIAction.REDACT

        with record_span(
            "security.pii_scan",
            **{RAGAttributes.PROVIDER: self._cfg.provider},
        ) as span:
            if not self._cfg.enabled:
                # Local dev mode — skip DLP entirely
                return PIIDetectionResult(clean_text=text)

            result = await self._run_dlp(text, effective_action)

            if self._cfg.log_finding_types and result.findings:
                # Log TYPE only — the value must never appear in logs
                log.info(
                    "pii.detected",
                    types=[f.info_type for f in result.findings],
                    count=sum(f.count for f in result.findings),
                )

            span.set_attribute("rag.pii.types_found", len(result.findings))
            span.set_attribute("rag.pii.was_modified", result.was_modified)

            self._record_metrics(result)

            if result.findings and effective_action not in _REDACTION_ACTIONS:
                raise PIIDetectedError(result.pii_types)

            return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_dlp(self, text: str, action: PIIAction) -> PIIDetectionResult:
        """Delegate to Cloud DLP in a thread so the event loop is never blocked."""
        client = self._get_client()
        if action in _REDACTION_ACTIONS:
            return await asyncio.to_thread(self._deidentify, client, text)
        return await asyncio.to_thread(self._inspect, client, text)

    def _get_client(self) -> Any:
        if self._dlp_client is not None:
            return self._dlp_client
        try:
            from google.cloud import dlp_v2

            self._dlp_client = dlp_v2.DlpServiceClient()
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-dlp is required for PII detection. "
                "Install it with: pip install google-cloud-dlp"
            ) from exc
        return self._dlp_client

    def _inspect(self, client: Any, text: str) -> PIIDetectionResult:
        """Call DLP inspect_content and return findings (no modification)."""
        parent = self._dlp_parent()
        item = {"value": text}
        inspect_config = {
            "info_types": [{"name": t} for t in UK_INFO_TYPES],
            "min_likelihood": "LIKELY",
            "include_quote": False,  # CRITICAL: never include the actual PII value
        }
        response = client.inspect_content(
            request={"parent": parent, "inspect_config": inspect_config, "item": item}
        )
        findings = _parse_findings(response.result.findings)
        return PIIDetectionResult(
            clean_text=text,
            findings=findings,
            was_modified=False,
        )

    def _deidentify(self, client: Any, text: str) -> PIIDetectionResult:
        """Call DLP deidentify_content and return redacted text with finding summary."""
        parent = self._dlp_parent()
        item = {"value": text}
        inspect_config = {
            "info_types": [{"name": t} for t in UK_INFO_TYPES],
            "min_likelihood": "LIKELY",
        }
        deidentify_config = {
            "info_type_transformations": {
                "transformations": [
                    {
                        "primitive_transformation": {
                            "replace_with_info_type_config": {}
                        }
                    }
                ]
            }
        }
        response = client.deidentify_content(
            request={
                "parent": parent,
                "deidentify_config": deidentify_config,
                "inspect_config": inspect_config,
                "item": item,
            }
        )
        clean_text: str = response.item.value
        findings = _parse_transformation_summary(response.overview.transformation_summaries)
        return PIIDetectionResult(
            clean_text=clean_text,
            findings=findings,
            was_modified=clean_text != text,
        )

    def _dlp_parent(self) -> str:
        project_id = self._cfg.project_id
        if not project_id:
            raise ValueError(
                "security.pii_detection.project_id must be set when DLP is enabled."
            )
        return f"projects/{project_id}/locations/global"

    def _record_metrics(self, result: PIIDetectionResult) -> None:
        try:
            from rag.observability.metrics import get_metrics

            m = get_metrics()
            for finding in result.findings:
                m.pii_detections_total.add(
                    finding.count,
                    {"pii_type": finding.info_type},
                )
        except RuntimeError:
            pass  # metrics not configured (dev/test) — acceptable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REDACTION_ACTIONS: frozenset[PIIAction] = frozenset(
    {PIIAction.REDACT, PIIAction.REPLACE_WITH_INFO_TYPE, PIIAction.MASK, PIIAction.ENCRYPT}
)


def _parse_findings(raw_findings: Any) -> list[PIIFinding]:
    """Convert DLP Finding protos to PIIFinding (type + count only)."""
    counts: dict[str, int] = {}
    for finding in raw_findings:
        info_type = finding.info_type.name
        counts[info_type] = counts.get(info_type, 0) + 1
    return [PIIFinding(info_type=t, count=c) for t, c in counts.items()]


def _parse_transformation_summary(summaries: Any) -> list[PIIFinding]:
    """Convert DLP TransformationSummary protos to PIIFinding."""
    findings: list[PIIFinding] = []
    for summary in summaries:
        info_type = summary.info_type.name if summary.info_type.name else "UNKNOWN"
        transformed = summary.transformed_bytes
        # transformed_bytes is the byte count of transformed text;
        # use result_summary count if available (SDK ≥ 3.x)
        count = getattr(summary, "transformation_count", 1) if transformed > 0 else 0
        if count > 0:
            findings.append(PIIFinding(info_type=info_type, count=count))
    return findings
