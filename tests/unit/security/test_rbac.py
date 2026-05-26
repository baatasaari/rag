"""
Tests for rag.security.rbac — clearance, role gating, AccessDeniedError.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from rag.core.exceptions import AccessDeniedError
from rag.core.schemas import DataClassificationLevel, SecurityConfig
from rag.security.rbac import RBACEnforcer, UserContext, _CLEARANCE_ORDER


# ── Fixtures ──────────────────────────────────────────────────────────────────


@dataclass
class FakeDoc:
    """Minimal RBACDocument implementation for testing."""

    doc_id: str
    classification_level: DataClassificationLevel
    allowed_roles: frozenset[str]
    content: str = "content"


def _make_rbac_config(*, enabled: bool = True, enforce_at_retrieval: bool = True) -> SecurityConfig:
    cfg = MagicMock()
    cfg.rbac.enabled = enabled
    cfg.rbac.enforce_at_retrieval = enforce_at_retrieval
    return cfg


def _make_user(
    *,
    roles: frozenset[str] | None = None,
    clearance: DataClassificationLevel = DataClassificationLevel.INTERNAL,
    user_id: str = "user1",
) -> UserContext:
    return UserContext(
        user_id=user_id,
        roles=roles or frozenset({"analyst"}),
        classification_clearance=clearance,
    )


def _make_enforcer(*, enabled: bool = True, enforce_at_retrieval: bool = True) -> RBACEnforcer:
    return RBACEnforcer(_make_rbac_config(enabled=enabled, enforce_at_retrieval=enforce_at_retrieval))


# ── Clearance ordering ────────────────────────────────────────────────────────


class TestClearanceOrdering:
    def test_public_is_lowest(self):
        assert _CLEARANCE_ORDER[DataClassificationLevel.PUBLIC] == 0

    def test_restricted_is_highest(self):
        assert _CLEARANCE_ORDER[DataClassificationLevel.RESTRICTED] == 3

    def test_internal_between_public_and_confidential(self):
        assert (
            _CLEARANCE_ORDER[DataClassificationLevel.PUBLIC]
            < _CLEARANCE_ORDER[DataClassificationLevel.INTERNAL]
            < _CLEARANCE_ORDER[DataClassificationLevel.CONFIDENTIAL]
        )

    def test_all_levels_covered(self):
        for lvl in DataClassificationLevel:
            assert lvl in _CLEARANCE_ORDER


# ── UserContext ───────────────────────────────────────────────────────────────


class TestUserContext:
    def test_clearance_rank_public(self):
        user = _make_user(clearance=DataClassificationLevel.PUBLIC)
        assert user.clearance_rank == 0

    def test_clearance_rank_restricted(self):
        user = _make_user(clearance=DataClassificationLevel.RESTRICTED)
        assert user.clearance_rank == 3

    def test_user_context_is_frozen(self):
        user = _make_user()
        with pytest.raises((AttributeError, TypeError)):
            user.user_id = "hacked"  # type: ignore[misc]


# ── Basic enforcement ─────────────────────────────────────────────────────────


class TestBasicEnforcement:
    def test_user_sees_docs_within_clearance(self):
        enforcer = _make_enforcer()
        user = _make_user(clearance=DataClassificationLevel.INTERNAL, roles=frozenset({"analyst"}))
        docs = [
            FakeDoc("d1", DataClassificationLevel.PUBLIC, frozenset()),
            FakeDoc("d2", DataClassificationLevel.INTERNAL, frozenset()),
        ]
        result = enforcer.enforce(user, docs)
        assert len(result) == 2

    def test_user_cannot_see_docs_above_clearance(self):
        # enforce_at_retrieval=False: clearance-blocked → empty list, no raise
        enforcer = _make_enforcer(enforce_at_retrieval=False)
        user = _make_user(clearance=DataClassificationLevel.INTERNAL)
        docs = [
            FakeDoc("d1", DataClassificationLevel.CONFIDENTIAL, frozenset()),
            FakeDoc("d2", DataClassificationLevel.RESTRICTED, frozenset()),
        ]
        result = enforcer.enforce(user, docs)
        assert result == []

    def test_restricted_clearance_sees_all_levels(self):
        enforcer = _make_enforcer()
        user = _make_user(clearance=DataClassificationLevel.RESTRICTED)
        docs = [
            FakeDoc("d1", DataClassificationLevel.PUBLIC, frozenset()),
            FakeDoc("d2", DataClassificationLevel.INTERNAL, frozenset()),
            FakeDoc("d3", DataClassificationLevel.CONFIDENTIAL, frozenset()),
            FakeDoc("d4", DataClassificationLevel.RESTRICTED, frozenset()),
        ]
        result = enforcer.enforce(user, docs)
        assert len(result) == 4

    def test_public_clearance_only_sees_public(self):
        enforcer = _make_enforcer()
        user = _make_user(clearance=DataClassificationLevel.PUBLIC)
        docs = [
            FakeDoc("d1", DataClassificationLevel.PUBLIC, frozenset()),
            FakeDoc("d2", DataClassificationLevel.INTERNAL, frozenset()),
        ]
        result = enforcer.enforce(user, docs)
        assert len(result) == 1
        assert result[0].doc_id == "d1"

    def test_order_of_visible_docs_preserved(self):
        enforcer = _make_enforcer()
        user = _make_user(clearance=DataClassificationLevel.INTERNAL)
        docs = [
            FakeDoc("a", DataClassificationLevel.INTERNAL, frozenset()),
            FakeDoc("b", DataClassificationLevel.PUBLIC, frozenset()),
            FakeDoc("c", DataClassificationLevel.INTERNAL, frozenset()),
        ]
        result = enforcer.enforce(user, docs)
        assert [d.doc_id for d in result] == ["a", "b", "c"]


# ── Role filtering ────────────────────────────────────────────────────────────


class TestRoleFiltering:
    def test_user_role_matches_doc_allowed_roles(self):
        enforcer = _make_enforcer()
        user = _make_user(roles=frozenset({"analyst", "viewer"}))
        docs = [FakeDoc("d1", DataClassificationLevel.INTERNAL, frozenset({"analyst"}))]
        result = enforcer.enforce(user, docs)
        assert len(result) == 1

    def test_user_role_mismatch_filters_doc(self):
        enforcer = _make_enforcer()
        user = _make_user(roles=frozenset({"viewer"}))
        docs = [FakeDoc("d1", DataClassificationLevel.INTERNAL, frozenset({"admin"}))]
        result = enforcer.enforce(user, docs)
        assert result == []

    def test_empty_allowed_roles_means_any_role_can_see(self):
        enforcer = _make_enforcer()
        user = _make_user(roles=frozenset({"analyst"}))
        docs = [FakeDoc("d1", DataClassificationLevel.INTERNAL, frozenset())]
        result = enforcer.enforce(user, docs)
        assert len(result) == 1

    def test_mixed_clearance_and_role_filtering(self):
        enforcer = _make_enforcer()
        user = _make_user(
            clearance=DataClassificationLevel.INTERNAL,
            roles=frozenset({"analyst"}),
        )
        docs = [
            FakeDoc("d1", DataClassificationLevel.PUBLIC, frozenset()),       # pass
            FakeDoc("d2", DataClassificationLevel.INTERNAL, frozenset({"analyst"})),  # pass
            FakeDoc("d3", DataClassificationLevel.INTERNAL, frozenset({"admin"})),    # blocked: role
            FakeDoc("d4", DataClassificationLevel.CONFIDENTIAL, frozenset()),         # blocked: clearance
        ]
        result = enforcer.enforce(user, docs)
        assert {d.doc_id for d in result} == {"d1", "d2"}


# ── AccessDeniedError ─────────────────────────────────────────────────────────


class TestAccessDeniedError:
    def test_all_docs_clearance_blocked_raises_access_denied(self):
        enforcer = _make_enforcer(enforce_at_retrieval=True)
        user = _make_user(clearance=DataClassificationLevel.INTERNAL)
        docs = [
            FakeDoc("d1", DataClassificationLevel.RESTRICTED, frozenset()),
            FakeDoc("d2", DataClassificationLevel.RESTRICTED, frozenset()),
        ]
        with pytest.raises(AccessDeniedError) as exc_info:
            enforcer.enforce(user, docs)
        err = exc_info.value
        assert "INTERNAL" in err.user_clearance
        assert "RESTRICTED" in err.required_clearance

    def test_all_docs_role_blocked_returns_empty_not_raise(self):
        """Role mismatch returns [] — does not raise AccessDeniedError."""
        enforcer = _make_enforcer(enforce_at_retrieval=True)
        user = _make_user(
            clearance=DataClassificationLevel.RESTRICTED,
            roles=frozenset({"viewer"}),
        )
        docs = [FakeDoc("d1", DataClassificationLevel.INTERNAL, frozenset({"admin"}))]
        result = enforcer.enforce(user, docs)
        assert result == []  # no raise

    def test_partial_clearance_block_does_not_raise(self):
        """If at least one doc is visible, no error is raised."""
        enforcer = _make_enforcer(enforce_at_retrieval=True)
        user = _make_user(clearance=DataClassificationLevel.INTERNAL)
        docs = [
            FakeDoc("d1", DataClassificationLevel.INTERNAL, frozenset()),
            FakeDoc("d2", DataClassificationLevel.RESTRICTED, frozenset()),
        ]
        result = enforcer.enforce(user, docs)
        assert len(result) == 1

    def test_access_denied_error_has_user_id_hash_not_raw(self):
        enforcer = _make_enforcer(enforce_at_retrieval=True)
        user = _make_user(clearance=DataClassificationLevel.INTERNAL, user_id="alice@lbg.com")
        docs = [FakeDoc("d1", DataClassificationLevel.RESTRICTED, frozenset())]
        with pytest.raises(AccessDeniedError) as exc_info:
            enforcer.enforce(user, docs)
        err = exc_info.value
        # Raw user ID must not appear in the error
        assert "alice@lbg.com" not in err.user_id_hash
        assert len(err.user_id_hash) == 16  # HMAC hash prefix

    def test_access_denied_error_is_json_serialisable(self):
        import json

        enforcer = _make_enforcer(enforce_at_retrieval=True)
        user = _make_user(clearance=DataClassificationLevel.INTERNAL)
        docs = [FakeDoc("d1", DataClassificationLevel.RESTRICTED, frozenset())]
        with pytest.raises(AccessDeniedError) as exc_info:
            enforcer.enforce(user, docs)
        json.dumps(exc_info.value.to_dict())

    def test_enforce_at_retrieval_false_no_raise_on_clearance_block(self):
        enforcer = _make_enforcer(enforce_at_retrieval=False)
        user = _make_user(clearance=DataClassificationLevel.INTERNAL)
        docs = [FakeDoc("d1", DataClassificationLevel.RESTRICTED, frozenset())]
        result = enforcer.enforce(user, docs)
        assert result == []  # filtered but no raise


# ── Disabled mode ─────────────────────────────────────────────────────────────


class TestDisabledEnforcement:
    def test_disabled_passes_all_docs_through(self):
        enforcer = _make_enforcer(enabled=False)
        user = _make_user(clearance=DataClassificationLevel.PUBLIC)
        docs = [
            FakeDoc("d1", DataClassificationLevel.RESTRICTED, frozenset({"admin"})),
            FakeDoc("d2", DataClassificationLevel.CONFIDENTIAL, frozenset({"admin"})),
        ]
        result = enforcer.enforce(user, docs)
        assert result == docs

    def test_disabled_returns_original_list_object(self):
        enforcer = _make_enforcer(enabled=False)
        user = _make_user()
        docs = [FakeDoc("d1", DataClassificationLevel.INTERNAL, frozenset())]
        result = enforcer.enforce(user, docs)
        assert result is docs


# ── Empty inputs ──────────────────────────────────────────────────────────────


class TestEmptyInputs:
    def test_empty_doc_list_returns_empty(self):
        enforcer = _make_enforcer()
        user = _make_user()
        result = enforcer.enforce(user, [])
        assert result == []

    def test_empty_doc_list_does_not_raise_access_denied(self):
        enforcer = _make_enforcer(enforce_at_retrieval=True)
        user = _make_user()
        result = enforcer.enforce(user, [])
        assert result == []
