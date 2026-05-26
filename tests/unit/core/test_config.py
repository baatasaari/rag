"""
Tests for rag.core.config — loader, singleton, secret resolution, validation.

Coverage targets:
  - Happy path: valid YAML loads and validates.
  - Environment overlays: development overrides correctly deep-merge.
  - Secret resolution: env vars, missing vars, partial substitution.
  - Validation failures: schema errors, cross-field constraints.
  - Singleton behaviour: get before load, reload atomicity.
  - Security: SecretStr fields never appear in repr/str.
  - Immutability: frozen config raises on mutation.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from rag.core.config import (
    _deep_merge,
    _resolve_all_placeholders,
    get_config,
    load_config,
    reload_config,
)
from rag.core.exceptions import (
    ConfigLoadError,
    ConfigNotLoadedError,
    ConfigValidationError,
    SecretResolutionError,
)
from rag.core.schemas import (
    ChunkingStrategy,
    EmbeddingTaskType,
    RAGConfig,
    RAGPattern,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


# ── Happy path ────────────────────────────────────────────────────────────────


class TestHappyPath:
    def test_load_valid_config_returns_ragconfig(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        assert isinstance(cfg, RAGConfig)

    def test_loaded_config_accessible_via_get_config(self, real_config_dir, minimal_env):
        load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        cfg = get_config()
        assert isinstance(cfg, RAGConfig)

    def test_default_chunking_strategy_is_hierarchical(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        assert cfg.chunking.strategy == ChunkingStrategy.HIERARCHICAL

    def test_embedding_task_types_are_asymmetric(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        assert cfg.embedding.task_types.ingestion == EmbeddingTaskType.RETRIEVAL_DOCUMENT
        assert cfg.embedding.task_types.query == EmbeddingTaskType.RETRIEVAL_QUERY
        assert cfg.embedding.task_types.ingestion != cfg.embedding.task_types.query

    def test_config_location_is_europe_west2(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        assert cfg.embedding.location == "europe-west2"
        assert cfg.generation.location == "europe-west2"


# ── Environment overlays ──────────────────────────────────────────────────────


class TestEnvironmentOverlays:
    def test_development_overlay_sets_naive_pattern(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        # dev overlay overrides pattern to 'naive'
        assert cfg.pipeline.pattern == RAGPattern.NAIVE

    def test_production_overlay_sets_adaptive_pattern(self, real_config_dir, minimal_env):
        cfg = load_config(env="production", config_dir=real_config_dir, _skip_secret_manager=True)
        assert cfg.pipeline.pattern == RAGPattern.ADAPTIVE

    def test_development_disables_circuit_breaker(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        assert cfg.resilience.circuit_breaker.enabled is False

    def test_production_enables_circuit_breaker(self, real_config_dir, minimal_env):
        cfg = load_config(env="production", config_dir=real_config_dir, _skip_secret_manager=True)
        assert cfg.resilience.circuit_breaker.enabled is True

    def test_overlay_does_not_wipe_unmentioned_keys(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        # chunking is not in dev overlay — should still have base defaults
        assert cfg.chunking.hierarchical.parent_chunk_size == 2048

    def test_no_overlay_file_loads_base_config(self, tmp_path, minimal_env):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              name: test-platform
              version: "1.0.0"
              pattern: naive
        """)
        # No environments/test.yaml — should load base only with a warning
        cfg = load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert cfg.pipeline.name == "test-platform"


# ── Deep merge ────────────────────────────────────────────────────────────────


class TestDeepMerge:
    def test_scalar_override(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 99}}
        result = _deep_merge(base, override)
        assert result["a"]["b"] == 99
        assert result["a"]["c"] == 2     # untouched

    def test_nested_dict_merged_not_replaced(self):
        base = {"x": {"y": {"z": 1, "w": 2}}}
        override = {"x": {"y": {"z": 99}}}
        result = _deep_merge(base, override)
        assert result["x"]["y"]["z"] == 99
        assert result["x"]["y"]["w"] == 2  # preserved

    def test_list_replaced_not_merged(self):
        # Lists are intentionally replaced wholesale (not extended).
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = _deep_merge(base, override)
        assert result["items"] == [4, 5]

    def test_new_key_added(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        original_base = {"a": {"b": 1}}
        _deep_merge(base, override)
        assert base == original_base


# ── Secret / placeholder resolution ──────────────────────────────────────────


class TestSecretResolution:
    def test_exact_placeholder_resolved_from_env(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "hello")
        data = {"key": "${MY_SECRET}"}
        resolved, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert resolved["key"] == "hello"
        assert errors == []

    def test_partial_placeholder_in_string(self, monkeypatch):
        monkeypatch.setenv("REGION", "europe-west2")
        data = {"endpoint": "https://api.${REGION}.example.com"}
        resolved, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert resolved["endpoint"] == "https://api.europe-west2.example.com"
        assert errors == []

    def test_missing_var_collected_not_raised(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        data = {"a": "${MISSING_VAR}", "b": "${ALSO_MISSING}"}
        _, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert "MISSING_VAR" in errors
        assert "ALSO_MISSING" in errors

    def test_same_var_referenced_twice_deduped(self, monkeypatch):
        monkeypatch.delenv("DUPE_VAR", raising=False)
        data = {"a": "${DUPE_VAR}", "b": "${DUPE_VAR}"}
        _, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert errors.count("DUPE_VAR") == 1

    def test_missing_vars_raise_secret_resolution_error(self, tmp_path, monkeypatch):
        monkeypatch.delenv("REQUIRED_VAR", raising=False)
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              name: test
              pattern: naive
            storage:
              vector_store:
                connection_string: ${REQUIRED_VAR}
        """)
        with pytest.raises(SecretResolutionError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "REQUIRED_VAR" in str(exc_info.value)

    def test_resolve_nested_dict(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "db.local")
        data = {"db": {"host": "${DB_HOST}", "port": 5432}}
        resolved, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert resolved["db"]["host"] == "db.local"
        assert resolved["db"]["port"] == 5432
        assert errors == []

    def test_resolve_list_of_placeholders(self, monkeypatch):
        monkeypatch.setenv("ITEM_A", "alpha")
        monkeypatch.setenv("ITEM_B", "beta")
        data = {"items": ["${ITEM_A}", "${ITEM_B}", "literal"]}
        resolved, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert resolved["items"] == ["alpha", "beta", "literal"]
        assert errors == []

    def test_non_string_values_pass_through(self, monkeypatch):
        data = {"count": 42, "enabled": True, "ratio": 0.5}
        resolved, errors = _resolve_all_placeholders(data, "development", skip_secret_manager=True)
        assert resolved == data
        assert errors == []


# ── Pydantic schema validation ────────────────────────────────────────────────


class TestSchemaValidation:
    def test_invalid_pattern_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              name: test
              pattern: not_a_real_pattern
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "pattern" in str(exc_info.value).lower()

    def test_overlap_gte_chunk_size_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            chunking:
              strategy: fixed
              fixed:
                chunk_size: 64
                overlap: 64      # must be < chunk_size
        """)
        with pytest.raises(ConfigValidationError):
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)

    def test_hierarchical_child_gte_parent_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            chunking:
              strategy: hierarchical
              hierarchical:
                parent_chunk_size: 512
                child_chunk_size: 512    # must be < parent
                overlap: 64
        """)
        with pytest.raises(ConfigValidationError):
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)

    def test_hybrid_weights_not_summing_to_one_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            retrieval:
              strategy: hybrid
              top_k: 10
              dense:
                weight: 0.6
              sparse:
                weight: 0.6    # 0.6 + 0.6 = 1.2, not 1.0
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "1.0" in str(exc_info.value)

    def test_ef_search_less_than_top_k_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            storage:
              vector_store:
                index:
                  type: hnsw
                  hnsw:
                    ef_search: 5    # must be >= retrieval.top_k
            retrieval:
              top_k: 20
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "ef_search" in str(exc_info.value)

    def test_reranker_top_n_gt_top_k_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            retrieval:
              top_k: 5
            augmentation:
              reranker:
                enabled: true
                top_n: 10    # must be <= top_k
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "top_n" in str(exc_info.value)

    def test_fast_path_dims_gte_default_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            embedding:
              dimensions:
                default: 256
                fast_path: 512    # must be < default
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "fast_path" in str(exc_info.value)

    def test_symmetric_embedding_task_types_raises(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            embedding:
              task_types:
                ingestion: RETRIEVAL_QUERY
                query: RETRIEVAL_QUERY    # same as ingestion — not allowed
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "asymmetric" in str(exc_info.value).lower() or "differ" in str(exc_info.value).lower()

    def test_all_pydantic_errors_reported_at_once(self, tmp_path):
        # Multiple validation errors should all appear in one exception.
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: not_valid
            embedding:
              dimensions:
                default: 256
                fast_path: 512
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        err = exc_info.value
        assert len(err.errors) >= 2, "Expected multiple errors to be reported"

    def test_agentic_strategy_requires_agentic_config(self, tmp_path):
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: naive
            chunking:
              strategy: agentic
              # agentic: block intentionally omitted
        """)
        with pytest.raises(ConfigValidationError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "agentic" in str(exc_info.value).lower()


# ── Singleton behaviour ───────────────────────────────────────────────────────


class TestSingleton:
    def test_get_before_load_raises_config_not_loaded(self):
        with pytest.raises(ConfigNotLoadedError) as exc_info:
            get_config()
        assert "load_config()" in str(exc_info.value)

    def test_second_load_replaces_singleton(self, real_config_dir, minimal_env, tmp_path):
        load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        first = get_config()

        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              name: replaced-platform
              pattern: naive
        """)
        load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        second = get_config()

        assert first is not second
        assert second.pipeline.name == "replaced-platform"

    def test_reload_replaces_singleton_atomically(self, real_config_dir, minimal_env, tmp_path):
        load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              name: reloaded
              pattern: naive
        """)
        reload_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert get_config().pipeline.name == "reloaded"

    def test_reload_preserves_old_config_on_failure(self, real_config_dir, minimal_env, tmp_path):
        load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        original = get_config()

        _write_yaml(tmp_path, "rag_config.yaml", """
            pipeline:
              pattern: not_valid_pattern
        """)
        with pytest.raises(ConfigValidationError):
            reload_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)

        # Old config must still be active after failed reload.
        assert get_config() is original

    def test_config_not_loaded_error_message_is_helpful(self):
        with pytest.raises(ConfigNotLoadedError) as exc_info:
            get_config()
        msg = str(exc_info.value)
        assert "load_config()" in msg
        assert "RAG_ENV" in msg


# ── Immutability ──────────────────────────────────────────────────────────────


class TestImmutability:
    def test_config_is_frozen(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        with pytest.raises(Exception):  # pydantic.ValidationError or dataclasses.FrozenInstanceError
            cfg.pipeline.name = "hacked"  # type: ignore[misc]

    def test_nested_config_is_frozen(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        with pytest.raises(Exception):
            cfg.embedding.dimensions.default = 9999  # type: ignore[misc]


# ── SecretStr ─────────────────────────────────────────────────────────────────


class TestSecretStr:
    def test_connection_string_not_in_repr(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        if cfg.storage.vector_store.connection_string:
            repr_str = repr(cfg.storage.vector_store.connection_string)
            assert "pass" not in repr_str
            assert "password" not in repr_str.lower()

    def test_secret_str_repr_shows_redacted(self, real_config_dir, minimal_env):
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        if cfg.storage.vector_store.connection_string:
            assert "**" in repr(cfg.storage.vector_store.connection_string)

    def test_full_config_repr_does_not_leak_secrets(self, real_config_dir, minimal_env, monkeypatch):
        monkeypatch.setenv("ALLOYDB_CONNECTION", "postgresql://user:supersecret@host/db")
        cfg = load_config(env="development", config_dir=real_config_dir, _skip_secret_manager=True)
        full_repr = repr(cfg)
        assert "supersecret" not in full_repr


# ── Error cases ───────────────────────────────────────────────────────────────


class TestErrorCases:
    def test_invalid_environment_name_raises(self, real_config_dir):
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(env="invalid_env", config_dir=real_config_dir, _skip_secret_manager=True)
        assert "invalid_env" in str(exc_info.value)

    def test_missing_config_dir_raises(self):
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(env="development", config_dir="/nonexistent/path", _skip_secret_manager=True)
        assert "not found" in str(exc_info.value).lower()

    def test_missing_base_config_file_raises(self, tmp_path):
        # Directory exists but rag_config.yaml is absent.
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "not found" in str(exc_info.value).lower()

    def test_malformed_yaml_raises_config_load_error(self, tmp_path):
        bad_yaml = tmp_path / "rag_config.yaml"
        bad_yaml.write_text("pipeline:\n  name: test\n  bad: [unclosed")
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert isinstance(exc_info.value, ConfigLoadError)

    def test_yaml_root_not_dict_raises(self, tmp_path):
        bad_yaml = tmp_path / "rag_config.yaml"
        bad_yaml.write_text("- item1\n- item2\n")
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert "mapping" in str(exc_info.value).lower()

    def test_config_load_error_carries_file_path(self, tmp_path):
        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(env="development", config_dir=tmp_path, _skip_secret_manager=True)
        assert exc_info.value.file_path != ""

    def test_error_is_json_serialisable(self, real_config_dir):
        import json
        try:
            load_config(env="invalid_env", config_dir=real_config_dir, _skip_secret_manager=True)
        except ConfigLoadError as exc:
            as_dict = exc.to_dict()
            json.dumps(as_dict)  # must not raise
