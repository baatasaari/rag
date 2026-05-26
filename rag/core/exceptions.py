"""
Typed exception hierarchy for the LBG RAG Platform.

Every exception:
  - Carries a `component` field (which subsystem raised it).
  - Carries a `context` dict (structured key/value detail for logging).
  - Is JSON-serialisable via `to_dict()`.
  - Never swallows the original cause — always chain with `raise X from cause`.

Usage:
    raise ConfigValidationError(
        "embedding.dimensions.fast_path must be < default",
        component="config",
        context={"fast_path": 512, "default": 256},
    ) from original_pydantic_error
"""

from __future__ import annotations

from typing import Any


# ── Base ──────────────────────────────────────────────────────────────────────


class RAGPlatformError(Exception):
    """Root exception for all LBG RAG platform errors."""

    def __init__(
        self,
        message: str,
        component: str = "unknown",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.component = component
        self.context: dict[str, Any] = context or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": type(self).__name__,
            "message": str(self),
            "component": self.component,
            "context": self.context,
        }

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"message={str(self)!r}, "
            f"component={self.component!r}, "
            f"context={self.context!r})"
        )


# ── Config errors ─────────────────────────────────────────────────────────────


class ConfigError(RAGPlatformError):
    """Base for all configuration-related errors."""


class ConfigNotLoadedError(ConfigError):
    """Raised when `get_config()` is called before `load_config()`."""

    def __init__(self) -> None:
        super().__init__(
            "Configuration has not been loaded. "
            "Call rag.core.config.load_config() before accessing get_config(). "
            "In application startup: load_config(env=os.getenv('RAG_ENV', 'development')).",
            component="config",
        )


class ConfigLoadError(ConfigError):
    """YAML parsing failed or the config file could not be read."""

    def __init__(
        self,
        message: str,
        file_path: str = "",
        line: int | None = None,
    ) -> None:
        ctx: dict[str, Any] = {"file_path": file_path}
        if line is not None:
            ctx["line"] = line
        super().__init__(message, component="config", context=ctx)
        self.file_path = file_path
        self.line = line


class ConfigValidationError(ConfigError):
    """Pydantic schema validation failed.

    `errors` is the list of Pydantic-style error dicts so callers can render
    all problems at once rather than one-at-a-time.
    """

    def __init__(
        self,
        message: str,
        errors: list[dict[str, Any]] | None = None,
        environment: str = "",
    ) -> None:
        super().__init__(
            message,
            component="config",
            context={"errors": errors or [], "environment": environment},
        )
        self.errors = errors or []
        self.environment = environment


class SecretResolutionError(ConfigError):
    """One or more `${VAR_NAME}` placeholders could not be resolved.

    All unresolvable variables are collected before raising so the
    developer sees the full list in one error, not one-at-a-time.
    """

    def __init__(self, unresolved: list[str], environment: str = "") -> None:
        formatted = "\n  ".join(f"${{{v}}}" for v in unresolved)
        super().__init__(
            f"Cannot resolve {len(unresolved)} config placeholder(s):\n  {formatted}\n"
            f"Set these as environment variables or in GCP Secret Manager "
            f"(secret name = lowercase with hyphens, e.g. MY_VAR → my-var).",
            component="config",
            context={"unresolved_vars": unresolved, "environment": environment},
        )
        self.unresolved = unresolved
        self.environment = environment


class ConfigMutationError(ConfigError):
    """Raised when code attempts to mutate the frozen config singleton."""

    def __init__(self, field: str = "") -> None:
        super().__init__(
            f"Config is immutable after load. "
            f"Attempted mutation on field: {field!r}. "
            f"To apply new settings call reload_config().",
            component="config",
            context={"field": field},
        )


# ── Registry errors ───────────────────────────────────────────────────────────


class PluginError(RAGPlatformError):
    """Base for all plugin registry errors."""


class PluginNotFoundError(PluginError):
    """A lookup was attempted for a name that has not been registered."""

    def __init__(
        self,
        component_type: str,
        name: str,
        available: list[str] | None = None,
    ) -> None:
        avail_str = (
            f"Available: {available}" if available else "No plugins registered for this type."
        )
        super().__init__(
            f"No plugin registered for component_type={component_type!r}, name={name!r}. "
            f"{avail_str}",
            component="registry",
            context={
                "component_type": component_type,
                "requested_name": name,
                "available": available or [],
            },
        )
        self.component_type = component_type
        self.name = name
        self.available = available or []


class PluginConflictError(PluginError):
    """Two plugins attempted to register under the same (component_type, name) key."""

    def __init__(
        self,
        component_type: str,
        name: str,
        existing_cls: type,
        new_cls: type,
    ) -> None:
        super().__init__(
            f"Duplicate plugin registration for component_type={component_type!r}, "
            f"name={name!r}. "
            f"Already registered: {existing_cls.__qualname__}. "
            f"Attempted re-registration: {new_cls.__qualname__}. "
            f"Use a unique name or explicitly deregister the existing plugin first.",
            component="registry",
            context={
                "component_type": component_type,
                "name": name,
                "existing_class": existing_cls.__qualname__,
                "new_class": new_cls.__qualname__,
            },
        )
        self.component_type = component_type
        self.name = name


class PluginTypeError(PluginError):
    """A registered class does not implement the required base/protocol."""

    def __init__(
        self,
        component_type: str,
        name: str,
        cls: type,
        required_base: type,
        missing_methods: list[str],
    ) -> None:
        super().__init__(
            f"Plugin {cls.__qualname__!r} (component_type={component_type!r}, "
            f"name={name!r}) does not implement required base {required_base.__qualname__!r}. "
            f"Missing methods: {missing_methods}.",
            component="registry",
            context={
                "component_type": component_type,
                "name": name,
                "class": cls.__qualname__,
                "required_base": required_base.__qualname__,
                "missing_methods": missing_methods,
            },
        )
        self.missing_methods = missing_methods


class RegistryFrozenError(PluginError):
    """Mutation of the registry was attempted after freeze()."""

    def __init__(self, attempted_operation: str = "register") -> None:
        super().__init__(
            f"Registry is frozen and cannot be mutated. "
            f"Attempted operation: {attempted_operation!r}. "
            f"All plugins must be registered before freeze() is called at application startup.",
            component="registry",
            context={"attempted_operation": attempted_operation},
        )


class MissingProviderError(PluginError):
    """Config references a provider that has not been registered.

    Raised by `validate_against_config()` — all missing providers are
    collected before raising so the full list is visible at once.
    """

    def __init__(self, missing: list[dict[str, str]]) -> None:
        lines = "\n  ".join(
            f"component_type={m['component_type']!r}, name={m['name']!r} "
            f"(config field: {m['config_field']})"
            for m in missing
        )
        super().__init__(
            f"{len(missing)} provider(s) referenced in config are not registered:\n  {lines}\n"
            f"Ensure all plugin modules are imported before calling validate_against_config().",
            component="registry",
            context={"missing_providers": missing},
        )
        self.missing = missing


# ── Runtime / pipeline errors ─────────────────────────────────────────────────


class RAGPipelineError(RAGPlatformError):
    """Base for errors that occur during query or ingestion execution."""


class EmbeddingError(RAGPipelineError):
    def __init__(self, message: str, provider: str = "", model: str = "", **ctx: Any) -> None:
        super().__init__(message, component="embedding", context={"provider": provider, "model": model, **ctx})


class RetrievalError(RAGPipelineError):
    def __init__(self, message: str, strategy: str = "", **ctx: Any) -> None:
        super().__init__(message, component="retrieval", context={"strategy": strategy, **ctx})


class GenerationError(RAGPipelineError):
    def __init__(self, message: str, provider: str = "", model: str = "", **ctx: Any) -> None:
        super().__init__(message, component="generation", context={"provider": provider, "model": model, **ctx})


class IngestionError(RAGPipelineError):
    def __init__(self, message: str, source_uri: str = "", stage: str = "", **ctx: Any) -> None:
        super().__init__(message, component="ingestion", context={"source_uri": source_uri, "stage": stage, **ctx})


class StorageError(RAGPipelineError):
    def __init__(self, message: str, store_type: str = "", **ctx: Any) -> None:
        super().__init__(message, component="storage", context={"store_type": store_type, **ctx})


class CircuitBreakerOpenError(RAGPipelineError):
    """Raised when a circuit breaker is open and the call is rejected."""

    def __init__(self, component: str, retry_after_seconds: float | None = None) -> None:
        ctx: dict[str, Any] = {"component": component}
        if retry_after_seconds is not None:
            ctx["retry_after_seconds"] = retry_after_seconds
        super().__init__(
            f"Circuit breaker OPEN for component {component!r}. "
            f"Calls are being rejected to protect downstream service. "
            + (f"Retry after {retry_after_seconds:.0f}s." if retry_after_seconds else ""),
            component="resilience",
            context=ctx,
        )


# ── Security errors ───────────────────────────────────────────────────────────


class SecurityError(RAGPlatformError):
    """Base for all security-related errors."""


class PIIDetectedError(SecurityError):
    """Raised when PII is found in text that must be PII-free.

    Only carries the PII *types* found — the actual values are never stored.
    """

    def __init__(self, pii_types: list[str]) -> None:
        formatted = ", ".join(pii_types)
        super().__init__(
            f"PII detected in input ({formatted}). Request blocked to protect sensitive data. "
            f"Remove all personally identifiable information before resubmitting.",
            component="security",
            context={"pii_types": pii_types},
        )
        self.pii_types = pii_types


class AccessDeniedError(SecurityError):
    """Raised when a user's clearance level is insufficient for a requested operation."""

    def __init__(
        self,
        user_id_hash: str = "",
        required_clearance: str = "",
        user_clearance: str = "",
        resource_id: str = "",
    ) -> None:
        super().__init__(
            f"Access denied: user clearance {user_clearance!r} is insufficient "
            f"(required: {required_clearance!r}).",
            component="security",
            context={
                "user_id_hash": user_id_hash,
                "required_clearance": required_clearance,
                "user_clearance": user_clearance,
                "resource_id": resource_id,
            },
        )
        self.user_id_hash = user_id_hash
        self.required_clearance = required_clearance
        self.user_clearance = user_clearance


class AuditLogError(SecurityError):
    """Raised when the audit log fails to write.

    A failed audit write is treated as a security incident — never silenced.
    """

    def __init__(self, message: str, backend: str = "", event_id: str = "") -> None:
        super().__init__(
            message,
            component="audit",
            context={"backend": backend, "event_id": event_id},
        )
        self.backend = backend
        self.event_id = event_id
