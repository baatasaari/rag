"""
Tests for rag.pipeline.context — QueryContext.
"""

from __future__ import annotations

import pytest

from rag.pipeline.context import QueryContext


class TestQueryContext:
    def test_query_id_auto_generated(self):
        ctx = QueryContext(query="q", user_id="u1", allowed_roles=frozenset(["employee"]))
        assert isinstance(ctx.query_id, str)
        assert len(ctx.query_id) == 32  # uuid4 hex

    def test_two_contexts_have_different_query_ids(self):
        ctx1 = QueryContext(query="q", user_id="u", allowed_roles=frozenset())
        ctx2 = QueryContext(query="q", user_id="u", allowed_roles=frozenset())
        assert ctx1.query_id != ctx2.query_id

    def test_explicit_query_id_preserved(self):
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset(), query_id="abc123")
        assert ctx.query_id == "abc123"

    def test_defaults(self):
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset())
        assert ctx.session_id is None
        assert ctx.filters is None
        assert ctx.top_k is None
        assert ctx.stream is False
        assert ctx.metadata == {}

    def test_frozen_raises_on_mutation(self):
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset())
        with pytest.raises((AttributeError, TypeError)):
            ctx.query = "mutated"  # type: ignore[misc]

    def test_allowed_roles_is_frozenset(self):
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset(["a", "b"]))
        assert isinstance(ctx.allowed_roles, frozenset)

    def test_filters_accepted(self):
        ctx = QueryContext(
            query="q", user_id="u",
            allowed_roles=frozenset(),
            filters={"doc_type": "policy"},
        )
        assert ctx.filters == {"doc_type": "policy"}

    def test_top_k_override(self):
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset(), top_k=3)
        assert ctx.top_k == 3

    def test_stream_flag(self):
        ctx = QueryContext(query="q", user_id="u", allowed_roles=frozenset(), stream=True)
        assert ctx.stream is True
