"""
Stage 10: RBAC Tag Application

Maps ctx.classification_level to a list of allowed_roles that must appear on
every stored chunk.  The role hierarchy is LBG-policy-aligned:

  PUBLIC      → public, employee, manager, analyst, admin
  INTERNAL    → employee, manager, analyst, admin
  CONFIDENTIAL→ manager, analyst, admin
  RESTRICTED  → admin

If PIIDetectionConfig.reject_restricted_data is True (default), RESTRICTED
documents are aborted here — they are never stored.

Sets ctx.allowed_roles.
"""

from __future__ import annotations

from rag.core.schemas import DataClassificationLevel
from rag.ingestion.context import IngestionContext
from rag.observability.logging import get_logger

log = get_logger(__name__)

_ROLE_MAP: dict[DataClassificationLevel, list[str]] = {
    DataClassificationLevel.PUBLIC: ["public", "employee", "manager", "analyst", "admin"],
    DataClassificationLevel.INTERNAL: ["employee", "manager", "analyst", "admin"],
    DataClassificationLevel.CONFIDENTIAL: ["manager", "analyst", "admin"],
    DataClassificationLevel.RESTRICTED: ["admin"],
}


def apply_rbac(
    ctx: IngestionContext,
    *,
    reject_restricted: bool = True,
) -> IngestionContext:
    """Map classification level to allowed_roles.

    Args:
        ctx:               Current pipeline context.
        reject_restricted: Abort pipeline if classification is RESTRICTED.
                           Mirrors PIIDetectionConfig.reject_restricted_data.

    Returns:
        Updated context with ctx.allowed_roles set.
    """
    level = ctx.classification_level
    ctx.allowed_roles = list(_ROLE_MAP.get(level, ["admin"]))

    if level == DataClassificationLevel.RESTRICTED and reject_restricted:
        ctx.abort(
            f"RESTRICTED document rejected by policy "
            f"(source_uri={ctx.source_uri!r}). "
            "Override PIIDetectionConfig.reject_restricted_data to allow."
        )
        log.warning(
            "ingestion.rbac.restricted_rejected",
            source_uri=ctx.source_uri,
        )
    else:
        log.info(
            "ingestion.rbac.ok",
            source_uri=ctx.source_uri,
            classification_level=level.value,
            allowed_roles=ctx.allowed_roles,
        )

    return ctx
