"""
Tests for rag.core.registry — plugin registration, lookup, freeze, validation.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rag.core.exceptions import (
    MissingProviderError,
    PluginConflictError,
    PluginNotFoundError,
    PluginTypeError,
    RegistryFrozenError,
)
from rag.core.registry import (
    COMPONENT_TYPES,
    freeze,
    get,
    is_frozen,
    list_registered,
    register,
    reset,
    set_required_base,
    validate_against_config,
)


# ── Basic registration and lookup ─────────────────────────────────────────────


class TestRegisterAndLookup:
    def test_register_and_get_returns_class(self):
        @register("chunking", "test_chunker")
        class TestChunker:
            pass

        assert get("chunking", "test_chunker") is TestChunker

    def test_register_preserves_original_class(self):
        class OriginalClass:
            original_attr = "original"

        decorated = register("chunking", "preserved")(OriginalClass)
        assert decorated is OriginalClass
        assert decorated.original_attr == "original"

    def test_register_multiple_types_same_name(self):
        @register("chunking", "dual")
        class ChunkingImpl:
            pass

        @register("embedding", "dual")
        class EmbeddingImpl:
            pass

        assert get("chunking", "dual") is ChunkingImpl
        assert get("embedding", "dual") is EmbeddingImpl

    def test_register_multiple_names_same_type(self):
        @register("chunking", "alpha")
        class Alpha:
            pass

        @register("chunking", "beta")
        class Beta:
            pass

        assert get("chunking", "alpha") is Alpha
        assert get("chunking", "beta") is Beta

    def test_list_registered_returns_sorted_names(self):
        @register("llm", "zebra")
        class Z:
            pass

        @register("llm", "apple")
        class A:
            pass

        names = list_registered("llm")
        assert names == ["apple", "zebra"]

    def test_list_registered_empty_type_returns_empty(self):
        assert list_registered("tool") == []


# ── Error cases on lookup ─────────────────────────────────────────────────────


class TestLookupErrors:
    def test_lookup_unregistered_raises_plugin_not_found(self):
        with pytest.raises(PluginNotFoundError) as exc_info:
            get("chunking", "nonexistent")
        err = exc_info.value
        assert err.component_type == "chunking"
        assert err.name == "nonexistent"

    def test_not_found_error_includes_available_names(self):
        @register("chunking", "available_one")
        class One:
            pass

        with pytest.raises(PluginNotFoundError) as exc_info:
            get("chunking", "missing_one")
        assert "available_one" in exc_info.value.available

    def test_not_found_error_message_is_helpful(self):
        with pytest.raises(PluginNotFoundError) as exc_info:
            get("embedding", "mystery")
        msg = str(exc_info.value)
        assert "embedding" in msg
        assert "mystery" in msg

    def test_not_found_error_is_json_serialisable(self):
        import json
        with pytest.raises(PluginNotFoundError) as exc_info:
            get("chunking", "json_test")
        json.dumps(exc_info.value.to_dict())  # must not raise


# ── Conflict detection ────────────────────────────────────────────────────────


class TestConflictDetection:
    def test_duplicate_registration_raises_conflict_error(self):
        @register("chunking", "duplicate")
        class First:
            pass

        with pytest.raises(PluginConflictError) as exc_info:
            @register("chunking", "duplicate")
            class Second:
                pass

        err = exc_info.value
        assert err.component_type == "chunking"
        assert err.name == "duplicate"
        assert "First" in str(err)
        assert "Second" in str(err)

    def test_conflict_does_not_replace_original(self):
        @register("chunking", "keep_original")
        class Original:
            pass

        with pytest.raises(PluginConflictError):
            @register("chunking", "keep_original")
            class Impostor:
                pass

        assert get("chunking", "keep_original") is Original


# ── Type checking on registration ────────────────────────────────────────────


class TestTypeChecking:
    def test_missing_abstract_method_raises_plugin_type_error(self):
        from abc import ABC, abstractmethod

        class RequiredBase(ABC):
            @abstractmethod
            def required_method(self) -> str:
                ...

        set_required_base("tool", RequiredBase)

        with pytest.raises(PluginTypeError) as exc_info:
            @register("tool", "missing_method_tool")
            class Incomplete:
                pass  # does not implement required_method

        err = exc_info.value
        assert "required_method" in err.missing_methods

    def test_complete_implementation_registers_successfully(self):
        from abc import ABC, abstractmethod

        class Base(ABC):
            @abstractmethod
            def compute(self) -> int:
                ...

        set_required_base("tool", Base)

        @register("tool", "complete_tool")
        class Complete(Base):
            def compute(self) -> int:
                return 42

        assert get("tool", "complete_tool") is Complete

    def test_unknown_component_type_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            @register("not_a_real_type", "whatever")
            class X:
                pass
        assert "not_a_real_type" in str(exc_info.value)
        assert "COMPONENT_TYPES" in str(exc_info.value)


# ── Freeze behaviour ──────────────────────────────────────────────────────────


class TestFreeze:
    def test_register_after_freeze_raises(self):
        freeze()
        with pytest.raises(RegistryFrozenError) as exc_info:
            @register("chunking", "post_freeze")
            class Late:
                pass
        assert "frozen" in str(exc_info.value).lower()

    def test_get_still_works_after_freeze(self):
        @register("chunking", "pre_freeze")
        class Early:
            pass

        freeze()
        assert get("chunking", "pre_freeze") is Early

    def test_list_registered_works_after_freeze(self):
        @register("chunking", "listable")
        class Listable:
            pass

        freeze()
        names = list_registered("chunking")
        assert "listable" in names

    def test_is_frozen_reflects_state(self):
        assert not is_frozen()
        freeze()
        assert is_frozen()

    def test_reset_unfreezes(self):
        freeze()
        assert is_frozen()
        reset()
        assert not is_frozen()

    def test_set_required_base_after_freeze_raises(self):
        from abc import ABC
        freeze()
        with pytest.raises(RegistryFrozenError):
            set_required_base("chunking", ABC)

    def test_registry_frozen_error_message_describes_operation(self):
        freeze()
        with pytest.raises(RegistryFrozenError) as exc_info:
            @register("chunking", "too_late")
            class TooLate:
                pass
        assert "register" in str(exc_info.value)

    def test_frozen_error_is_json_serialisable(self):
        import json
        freeze()
        with pytest.raises(RegistryFrozenError) as exc_info:
            @register("chunking", "blocked")
            class Blocked:
                pass
        json.dumps(exc_info.value.to_dict())


# ── Config validation ─────────────────────────────────────────────────────────


class TestValidateAgainstConfig:
    def _make_config(self, **overrides):
        """Build a minimal mock config object."""
        defaults = {
            "chunking.strategy.value": "hierarchical",
            "embedding.provider.value": "vertex_ai",
            "embedding.fallback": None,
            "storage.vector_store.provider.value": "alloydb_pgvector",
            "storage.document_store.provider.value": "alloydb",
            "storage.graph_store": None,
            "retrieval.strategy.value": "hybrid",
            "retrieval.sparse.provider.value": "vertex_ai_search",
            "augmentation.reranker.enabled": False,
            "augmentation.reranker.provider.value": "cohere",
            "augmentation.reranker.fallback_provider": None,
            "generation.provider.value": "vertex_ai",
            "generation.fallback": None,
            "agents.tools": [],
        }
        defaults.update(overrides)

        cfg = MagicMock()
        cfg.chunking.strategy.value = defaults["chunking.strategy.value"]
        cfg.embedding.provider.value = defaults["embedding.provider.value"]
        cfg.embedding.fallback = defaults["embedding.fallback"]
        cfg.storage.vector_store.provider.value = defaults["storage.vector_store.provider.value"]
        cfg.storage.document_store.provider.value = defaults["storage.document_store.provider.value"]
        cfg.storage.graph_store = defaults["storage.graph_store"]
        cfg.retrieval.strategy.value = defaults["retrieval.strategy.value"]
        cfg.retrieval.sparse.provider.value = defaults["retrieval.sparse.provider.value"]
        cfg.augmentation.reranker.enabled = defaults["augmentation.reranker.enabled"]
        cfg.augmentation.reranker.provider.value = defaults["augmentation.reranker.provider.value"]
        cfg.augmentation.reranker.fallback_provider = defaults["augmentation.reranker.fallback_provider"]
        cfg.generation.provider.value = defaults["generation.provider.value"]
        cfg.generation.fallback = defaults["generation.fallback"]
        cfg.agents.tools = defaults["agents.tools"]
        return cfg

    def _register_all(self, names: list[tuple[str, str]]) -> None:
        for component_type, name in names:
            register(component_type, name)(type(f"Mock_{name}", (), {}))

    def test_all_registered_passes_validation(self):
        self._register_all([
            ("chunking", "hierarchical"),
            ("embedding", "vertex_ai"),
            ("vector_store", "alloydb_pgvector"),
            ("document_store", "alloydb"),
            ("retriever", "hybrid"),
            ("sparse_retriever", "vertex_ai_search"),
            ("llm", "vertex_ai"),
        ])
        cfg = self._make_config()
        validate_against_config(cfg)  # should not raise

    def test_missing_chunking_provider_raises(self):
        # Register everything except chunking.hierarchical.
        self._register_all([
            ("embedding", "vertex_ai"),
            ("vector_store", "alloydb_pgvector"),
            ("document_store", "alloydb"),
            ("retriever", "hybrid"),
            ("sparse_retriever", "vertex_ai_search"),
            ("llm", "vertex_ai"),
        ])
        cfg = self._make_config()
        with pytest.raises(MissingProviderError) as exc_info:
            validate_against_config(cfg)
        missing_names = [m["name"] for m in exc_info.value.missing]
        assert "hierarchical" in missing_names

    def test_all_missing_providers_reported_at_once(self):
        # Register nothing — all providers missing.
        cfg = self._make_config()
        with pytest.raises(MissingProviderError) as exc_info:
            validate_against_config(cfg)
        # Multiple providers should be listed in one error.
        assert len(exc_info.value.missing) >= 3

    def test_missing_provider_error_lists_config_field(self):
        cfg = self._make_config()
        with pytest.raises(MissingProviderError) as exc_info:
            validate_against_config(cfg)
        fields = {m["config_field"] for m in exc_info.value.missing}
        assert "chunking.strategy" in fields

    def test_optional_graph_store_not_validated_when_null(self):
        self._register_all([
            ("chunking", "hierarchical"),
            ("embedding", "vertex_ai"),
            ("vector_store", "alloydb_pgvector"),
            ("document_store", "alloydb"),
            ("retriever", "hybrid"),
            ("sparse_retriever", "vertex_ai_search"),
            ("llm", "vertex_ai"),
        ])
        cfg = self._make_config(**{"storage.graph_store": None})  # graph store disabled
        validate_against_config(cfg)  # should not raise — neo4j not required

    def test_missing_provider_error_is_json_serialisable(self):
        import json
        cfg = self._make_config()
        with pytest.raises(MissingProviderError) as exc_info:
            validate_against_config(cfg)
        json.dumps(exc_info.value.to_dict())


# ── Reset utility (used by conftest) ─────────────────────────────────────────


class TestReset:
    def test_reset_clears_registrations(self):
        @register("chunking", "to_be_cleared")
        class ToClear:
            pass

        assert get("chunking", "to_be_cleared") is ToClear
        reset()
        with pytest.raises(PluginNotFoundError):
            get("chunking", "to_be_cleared")

    def test_reset_unfreezes_registry(self):
        freeze()
        reset()
        @register("chunking", "after_reset")
        class AfterReset:
            pass
        assert get("chunking", "after_reset") is AfterReset
