"""
Configuration loader for the LBG RAG Platform.

Responsibilities:
  1. LOAD    — read base YAML + environment overlay, deep-merge them.
  2. INJECT  — resolve ${VAR_NAME} placeholders (env vars → Secret Manager).
  3. VALIDATE — run Pydantic schema validation, report ALL errors at once.
  4. EXPOSE  — thread-safe singleton `get_config()`.

Usage:
    # Application startup (e.g. api/main.py lifespan):
    from rag.core.config import load_config, get_config
    load_config()                 # reads RAG_ENV, finds YAML files, validates
    cfg = get_config()            # returns the frozen RAGConfig singleton

    # Hot-reload (admin API endpoint):
    from rag.core.config import reload_config
    reload_config()               # validates new config before swapping
"""

from __future__ import annotations

import logging
import os
import re
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from rag.core.exceptions import (
    ConfigLoadError,
    ConfigNotLoadedError,
    ConfigValidationError,
    SecretResolutionError,
)
from rag.core.schemas import RAGConfig

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_VALID_ENVIRONMENTS = frozenset({"development", "staging", "production"})
_PLACEHOLDER_EXACT = re.compile(r"^\$\{([^}]+)\}$")
_PLACEHOLDER_PARTIAL = re.compile(r"\$\{([^}]+)\}")

# ── Module-level state (private) ──────────────────────────────────────────────

_config: RAGConfig | None = None
_config_lock = threading.Lock()
_loading = threading.local()  # re-entrancy guard per thread

# ── Public API ────────────────────────────────────────────────────────────────


def load_config(
    env: str | None = None,
    config_dir: str | Path | None = None,
    *,
    _skip_secret_manager: bool = False,  # test seam — do not use in production
) -> RAGConfig:
    """Load, validate, and store the config singleton.

    Args:
        env:          Environment name. Defaults to RAG_ENV env var, then 'development'.
        config_dir:   Path to the config/ directory. Defaults to RAG_CONFIG_DIR env var,
                      then the config/ directory adjacent to the rag/ package root.
        _skip_secret_manager: Internal test flag. Skip GCP Secret Manager lookups.

    Returns:
        Frozen, validated RAGConfig singleton.

    Raises:
        ConfigLoadError:       YAML file not found or malformed.
        SecretResolutionError: One or more ${VAR} placeholders could not be resolved.
        ConfigValidationError: Pydantic schema validation failed.
    """
    global _config

    if getattr(_loading, "active", False):
        raise ConfigLoadError(
            "load_config() called re-entrantly — circular initialisation detected.",
            file_path="<unknown>",
        )

    with _config_lock:
        _loading.active = True
        try:
            resolved_env = _resolve_environment(env)
            resolved_dir = _resolve_config_dir(config_dir)
            raw = _load_and_merge_yaml(resolved_dir, resolved_env)
            injected, errors = _resolve_all_placeholders(
                raw, resolved_env, skip_secret_manager=_skip_secret_manager
            )
            if errors:
                raise SecretResolutionError(errors, environment=resolved_env)
            cfg = _validate(injected, resolved_env)
            _config = cfg
            logger.info(
                "Config loaded",
                extra={
                    "environment": resolved_env,
                    "pattern": cfg.pipeline.pattern.value,
                    "chunking_strategy": cfg.chunking.strategy.value,
                },
            )
            return cfg
        finally:
            _loading.active = False


def get_config() -> RAGConfig:
    """Return the loaded config singleton.

    Raises:
        ConfigNotLoadedError: If load_config() has not been called yet.
    """
    if _config is None:
        raise ConfigNotLoadedError()
    return _config


def reload_config(
    env: str | None = None,
    config_dir: str | Path | None = None,
    *,
    _skip_secret_manager: bool = False,
) -> RAGConfig:
    """Reload config atomically. Old config is preserved if validation fails.

    Safe to call from the admin API endpoint. The singleton is only replaced
    after the new config passes all validation.

    Raises:
        ConfigLoadError / SecretResolutionError / ConfigValidationError:
            Same as load_config(). Old config remains active on failure.
    """
    global _config

    resolved_env = _resolve_environment(env)
    resolved_dir = _resolve_config_dir(config_dir)
    raw = _load_and_merge_yaml(resolved_dir, resolved_env)
    injected, errors = _resolve_all_placeholders(
        raw, resolved_env, skip_secret_manager=_skip_secret_manager
    )
    if errors:
        raise SecretResolutionError(errors, environment=resolved_env)

    new_cfg = _validate(injected, resolved_env)

    with _config_lock:
        old_cfg = _config
        _config = new_cfg
        logger.info(
            "Config reloaded",
            extra={
                "environment": resolved_env,
                "old_pattern": old_cfg.pipeline.pattern.value if old_cfg else None,
                "new_pattern": new_cfg.pipeline.pattern.value,
            },
        )
    return new_cfg


# ── Internal helpers ──────────────────────────────────────────────────────────


def _resolve_environment(env: str | None) -> str:
    resolved = env or os.environ.get("RAG_ENV", "development")
    if resolved not in _VALID_ENVIRONMENTS:
        raise ConfigLoadError(
            f"Invalid environment: {resolved!r}. "
            f"Must be one of: {sorted(_VALID_ENVIRONMENTS)}.",
        )
    return resolved


def _resolve_config_dir(config_dir: str | Path | None) -> Path:
    if config_dir:
        path = Path(config_dir)
    elif raw := os.environ.get("RAG_CONFIG_DIR"):
        path = Path(raw)
    else:
        # Default: config/ directory at the project root (parent of the rag package).
        path = Path(__file__).parent.parent.parent / "config"

    if not path.is_dir():
        raise ConfigLoadError(
            f"Config directory not found: {path}. "
            f"Set RAG_CONFIG_DIR env var or pass config_dir= to load_config().",
            file_path=str(path),
        )
    return path


def _load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        raise ConfigLoadError(
            f"Config file not found: {path}",
            file_path=str(path),
        )
    except yaml.YAMLError as exc:
        line: int | None = None
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:  # type: ignore[union-attr]
            line = exc.problem_mark.line + 1  # type: ignore[union-attr]
        raise ConfigLoadError(
            f"YAML parse error in {path}: {exc}",
            file_path=str(path),
            line=line,
        ) from exc

    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"Expected a YAML mapping at the root of {path}, got {type(data).__name__}.",
            file_path=str(path),
        )
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` into `base`. Values in `override` win.

    Dicts are merged recursively. Scalars and lists are replaced wholesale.
    This preserves the base config's unmentioned keys while allowing the
    environment overlay to surgically change specific fields.
    """
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _load_and_merge_yaml(config_dir: Path, env: str) -> dict[str, Any]:
    base_path = config_dir / "rag_config.yaml"
    base = _load_yaml_file(base_path)

    env_path = config_dir / "environments" / f"{env}.yaml"
    if env_path.exists():
        overlay = _load_yaml_file(env_path)
        merged = _deep_merge(base, overlay)
        logger.debug("Applied environment overlay", extra={"overlay_path": str(env_path)})
        return merged

    if env != "development":
        logger.warning(
            "No environment overlay found for %r at %s. Using base config only.",
            env,
            env_path,
        )
    return base


def _resolve_all_placeholders(
    data: Any,
    environment: str,
    skip_secret_manager: bool = False,
) -> tuple[Any, list[str]]:
    """Walk the config tree and resolve all ${VAR_NAME} placeholders.

    Returns:
        (resolved_data, list_of_unresolved_var_names)

    All errors are collected before returning so the caller can surface the
    full list rather than one-at-a-time.
    """
    secret_cache: dict[str, str] = {}
    unresolved: list[str] = []

    def _resolve(value: Any) -> Any:
        if isinstance(value, str):
            # Full substitution: the entire string is a single placeholder.
            exact = _PLACEHOLDER_EXACT.fullmatch(value)
            if exact:
                var_name = exact.group(1)
                resolved = _lookup_var(var_name, secret_cache, environment, skip_secret_manager)
                if resolved is None:
                    unresolved.append(var_name)
                    return value  # keep original so validation errors are meaningful
                return resolved

            # Partial substitution: ${VAR} embedded within a larger string.
            def replacer(m: re.Match[str]) -> str:
                var_name = m.group(1)
                resolved = _lookup_var(var_name, secret_cache, environment, skip_secret_manager)
                if resolved is None:
                    unresolved.append(var_name)
                    return m.group(0)  # leave ${VAR} in place
                return str(resolved)

            return _PLACEHOLDER_PARTIAL.sub(replacer, value)

        if isinstance(value, dict):
            return {k: _resolve(v) for k, v in value.items()}

        if isinstance(value, list):
            return [_resolve(item) for item in value]

        return value

    resolved = _resolve(data)
    # Deduplicate while preserving order (same var referenced multiple times).
    seen: set[str] = set()
    unique_unresolved = [v for v in unresolved if not (v in seen or seen.add(v))]  # type: ignore[func-returns-value]
    return resolved, unique_unresolved


def _lookup_var(
    var_name: str,
    cache: dict[str, str],
    environment: str,
    skip_secret_manager: bool,
) -> str | None:
    # 1. Cache hit — avoids duplicate Secret Manager round-trips.
    if var_name in cache:
        return cache[var_name]

    # 2. Environment variable (always checked first — fast, no network).
    env_value = os.environ.get(var_name)
    if env_value is not None:
        cache[var_name] = env_value
        return env_value

    # 3. GCP Secret Manager (skipped in dev when flag is set, or if no project).
    if not skip_secret_manager:
        sm_value = _lookup_secret_manager(var_name, environment)
        if sm_value is not None:
            cache[var_name] = sm_value
            return sm_value

    return None


def _lookup_secret_manager(var_name: str, environment: str) -> str | None:
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        return None

    try:
        from google.cloud import secretmanager  # type: ignore[import-untyped]
        from google.api_core.exceptions import NotFound, PermissionDenied  # type: ignore[import-untyped]
    except ImportError:
        # google-cloud-secret-manager not installed (test environments).
        return None

    # Convention: MY_VAR_NAME → my-var-name (GCP secret naming convention).
    secret_name = var_name.lower().replace("_", "-")
    resource = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": resource})
        value = response.payload.data.decode("utf-8").strip()
        logger.debug("Resolved %s from Secret Manager", var_name)
        return value
    except NotFound:
        logger.debug("Secret %r not found in Secret Manager for project %s", secret_name, project_id)
        return None
    except PermissionDenied:
        logger.warning(
            "Permission denied accessing secret %r. "
            "Ensure the service account has roles/secretmanager.secretAccessor.",
            secret_name,
        )
        return None
    except Exception as exc:
        logger.debug("Secret Manager lookup failed for %s: %s", var_name, exc)
        return None


def _validate(data: dict[str, Any], environment: str) -> RAGConfig:
    try:
        return RAGConfig.model_validate(data)
    except ValidationError as exc:
        # Convert Pydantic errors to our typed exception.
        error_dicts: list[dict[str, Any]] = []
        for err in exc.errors():
            field_path = " → ".join(str(loc) for loc in err["loc"])
            error_dicts.append(
                {
                    "field": field_path,
                    "message": err["msg"],
                    "type": err["type"],
                    "input": str(err.get("input", ""))[:200],  # truncate large inputs
                }
            )

        summary_lines = [f"  [{e['field']}] {e['message']}" for e in error_dicts]
        raise ConfigValidationError(
            f"Config validation failed with {len(error_dicts)} error(s) "
            f"(environment={environment!r}):\n" + "\n".join(summary_lines),
            errors=error_dicts,
            environment=environment,
        ) from exc
