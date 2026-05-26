"""
Role-Based Access Control for the LBG RAG Platform.

Enforces document-level access at retrieval time.  The enforcement is
server-side and cannot be bypassed by callers — every document list that
leaves a vector store is passed through RBACEnforcer.enforce() before being
returned to any higher-level code.

Design:
  - UserContext carries identity (hashed for logging), roles, and clearance level.
  - RBACDocument is a Protocol: any retrieved document that exposes
    doc_id, classification_level, and allowed_roles satisfies it.
  - Clearance ordering: PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED
  - A document is accessible when BOTH conditions hold:
      1. user.clearance >= doc.classification_level  (clearance gate)
      2. user.roles ∩ doc.allowed_roles != ∅  OR  doc.allowed_roles is empty  (role gate)
  - AccessDeniedError is raised only when the user has zero accessible documents
    AND the requested resource explicitly requires a higher clearance.

Usage::

    enforcer = RBACEnforcer(config.security)
    visible_docs = enforcer.enforce(user_ctx, retrieved_docs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from rag.core.exceptions import AccessDeniedError
from rag.core.schemas import DataClassificationLevel, SecurityConfig
from rag.observability.logging import get_logger
from rag.observability.tracing import RAGAttributes, record_span

log = get_logger(__name__)

# Clearance ordering — higher index = higher clearance required
_CLEARANCE_ORDER: dict[DataClassificationLevel, int] = {
    DataClassificationLevel.PUBLIC: 0,
    DataClassificationLevel.INTERNAL: 1,
    DataClassificationLevel.CONFIDENTIAL: 2,
    DataClassificationLevel.RESTRICTED: 3,
}

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Protocols and data types
# ---------------------------------------------------------------------------


@runtime_checkable
class RBACDocument(Protocol):
    """Minimal interface every retrieved document must expose for RBAC filtering.

    Later modules (storage, retrieval) implement this on their document types.
    """

    @property
    def doc_id(self) -> str:
        ...

    @property
    def classification_level(self) -> DataClassificationLevel:
        ...

    @property
    def allowed_roles(self) -> frozenset[str]:
        ...


@dataclass(frozen=True)
class UserContext:
    """Identity and permission context for a single request.

    user_id is the raw identifier — it is HMAC-hashed before any log call
    or audit event.  Never pass raw user_id to get_logger() directly.
    """

    user_id: str
    roles: frozenset[str]
    classification_clearance: DataClassificationLevel
    session_id: str = ""

    @property
    def clearance_rank(self) -> int:
        return _CLEARANCE_ORDER.get(self.classification_clearance, 0)


# ---------------------------------------------------------------------------
# Enforcer
# ---------------------------------------------------------------------------


class RBACEnforcer:
    """Server-side RBAC enforcement.  Called by the retrieval layer before
    returning documents to the pipeline.
    """

    def __init__(self, config: SecurityConfig) -> None:
        self._cfg = config.rbac

    def enforce(
        self,
        user_ctx: UserContext,
        documents: list[Any],
    ) -> list[Any]:
        """Filter *documents* to those the user is authorised to see.

        Args:
            user_ctx:  Caller's identity, roles, and clearance.
            documents: Any list of objects that satisfy RBACDocument (have
                       doc_id, classification_level, allowed_roles).

        Returns:
            Subset of *documents* that pass both the clearance gate and the
            role gate.  Order is preserved.

        Raises:
            AccessDeniedError: If enforce_at_retrieval=True AND all documents
                were filtered out because the user lacks the minimum required
                clearance (not just role mismatch, which returns an empty list).
        """
        if not self._cfg.enabled:
            return documents

        from rag.observability.logging import _hmac_hash

        user_hash = _hmac_hash(user_ctx.user_id)

        with record_span(
            "security.rbac_enforce",
            **{
                RAGAttributes.QUERY_ID: user_ctx.session_id,
            },
        ) as span:
            visible: list[Any] = []
            clearance_blocked = 0
            role_blocked = 0

            for doc in documents:
                if not self._passes_clearance(user_ctx, doc):
                    clearance_blocked += 1
                    continue
                if not self._passes_role(user_ctx, doc):
                    role_blocked += 1
                    continue
                visible.append(doc)

            total_filtered = clearance_blocked + role_blocked
            span.set_attribute("rag.rbac.docs_total", len(documents))
            span.set_attribute("rag.rbac.docs_visible", len(visible))
            span.set_attribute("rag.rbac.docs_filtered", total_filtered)
            span.set_attribute("rag.rbac.clearance_blocked", clearance_blocked)
            span.set_attribute("rag.rbac.role_blocked", role_blocked)

            if total_filtered > 0:
                log.info(
                    "rbac.filtered",
                    user_id_hash=user_hash,
                    docs_total=len(documents),
                    docs_visible=len(visible),
                    clearance_blocked=clearance_blocked,
                    role_blocked=role_blocked,
                )

            # Raise AccessDeniedError only when enforce_at_retrieval is set AND
            # every document was blocked by clearance (not role — role mismatch
            # is a normal access pattern and returns an empty list gracefully).
            if (
                self._cfg.enforce_at_retrieval
                and documents
                and len(visible) == 0
                and clearance_blocked == len(documents)
            ):
                min_doc_level = self._minimum_clearance_required(documents)
                raise AccessDeniedError(
                    user_id_hash=user_hash,
                    required_clearance=min_doc_level.value,
                    user_clearance=user_ctx.classification_clearance.value,
                )

            return visible

    # ------------------------------------------------------------------
    # Gate helpers
    # ------------------------------------------------------------------

    def _passes_clearance(self, user_ctx: UserContext, doc: Any) -> bool:
        doc_level = getattr(doc, "classification_level", DataClassificationLevel.PUBLIC)
        doc_rank = _CLEARANCE_ORDER.get(doc_level, 0)
        return user_ctx.clearance_rank >= doc_rank

    def _passes_role(self, user_ctx: UserContext, doc: Any) -> bool:
        allowed: frozenset[str] = getattr(doc, "allowed_roles", frozenset())
        if not allowed:
            return True  # no role restriction — open to anyone with sufficient clearance
        return bool(user_ctx.roles & allowed)

    def _minimum_clearance_required(self, documents: list[Any]) -> DataClassificationLevel:
        """Return the lowest classification level among the given documents."""
        levels = [
            getattr(d, "classification_level", DataClassificationLevel.PUBLIC)
            for d in documents
        ]
        return min(levels, key=lambda lvl: _CLEARANCE_ORDER.get(lvl, 0))
