"""
Plugin registry for the LBG RAG Platform.

Every swappable component (chunker, embedder, vector store, LLM, etc.) is
registered here by name. The config references providers by name string;
the registry resolves those strings to concrete classes at runtime.

Lifecycle:
  1. Plugins register themselves at import time via @register().
  2. At application startup, after all plugin modules are imported,
     validate_against_config(cfg) is called to ensure every config-referenced
     provider has a registered implementation.
  3. freeze() is called to prevent further mutation during request handling.

Usage (plugin author):

    # rag/chunking/hierarchical.py
    from rag.core.registry import register

    @register("chunking", "hierarchical")
    class HierarchicalChunker:
        ...

Usage (caller):

    from rag.core.registry import get
    ChunkerCls = get("chunking", "hierarchical")
    chunker = ChunkerCls(config.chunking.hierarchical)
"""

from __future__ import annotations

import threading
from typing import Any

from rag.core.exceptions import (
    MissingProviderError,
    PluginConflictError,
    PluginNotFoundError,
    PluginTypeError,
    RegistryFrozenError,
)

# ── Known component types ─────────────────────────────────────────────────────
# Registering an unknown type is an error — catches typos early.

COMPONENT_TYPES: frozenset[str] = frozenset(
    {
        "chunking",
        "embedding",
        "vector_store",
        "document_store",
        "graph_store",
        "retriever",
        "sparse_retriever",
        "reranker",
        "compressor",
        "query_transformer",
        "llm",
        "rag_pattern",
        "loader",
        "parser",
        "cleaner",
        "enricher",
        "agent",
        "tool",
    }
)

# ── Module-level state (private) ──────────────────────────────────────────────

# Maps (component_type, name) → class.
_registry: dict[tuple[str, str], type] = {}

# Optional: maps component_type → required base class for type-checking on registration.
_required_bases: dict[str, type] = {}

_frozen: bool = False
_lock = threading.Lock()

# ── Public API ────────────────────────────────────────────────────────────────


def register(component_type: str, name: str, *, base: type | None = None):
    """Decorator that registers a class as a plugin implementation.

    Args:
        component_type: One of COMPONENT_TYPES (e.g. "chunking", "embedding").
        name:           Provider name as referenced in config YAML (e.g. "hierarchical").
        base:           Optional base class / protocol. If provided, the registered
                        class is checked to implement all abstract methods.

    Returns:
        Decorator that returns the original class unchanged.

    Raises:
        RegistryFrozenError:  If called after freeze().
        PluginConflictError:  If (component_type, name) is already registered.
        PluginTypeError:      If `base` is provided and the class is missing required methods.
        ValueError:           If component_type is not in COMPONENT_TYPES.

    Example:
        @register("chunking", "hierarchical")
        class HierarchicalChunker(ChunkingStrategyBase):
            ...
    """

    def decorator(cls: type) -> type:
        with _lock:
            if _frozen:
                raise RegistryFrozenError("register")

            if component_type not in COMPONENT_TYPES:
                raise ValueError(
                    f"Unknown component_type={component_type!r}. "
                    f"Must be one of: {sorted(COMPONENT_TYPES)}. "
                    f"Add it to COMPONENT_TYPES in rag/core/registry.py if this is intentional."
                )

            key = (component_type, name)
            if key in _registry:
                raise PluginConflictError(component_type, name, _registry[key], cls)

            # Type check against declared base class / protocol.
            effective_base = base or _required_bases.get(component_type)
            if effective_base is not None:
                missing = _missing_methods(cls, effective_base)
                if missing:
                    raise PluginTypeError(component_type, name, cls, effective_base, missing)

            _registry[key] = cls

        return cls  # decorator returns the class unchanged

    return decorator


def get(component_type: str, name: str) -> type:
    """Return the registered class for (component_type, name).

    Raises:
        PluginNotFoundError: With list of available names for the component type.
    """
    key = (component_type, name)
    cls = _registry.get(key)
    if cls is None:
        available = list_registered(component_type)
        raise PluginNotFoundError(component_type, name, available)
    return cls


def list_registered(component_type: str) -> list[str]:
    """Return sorted list of registered names for a component type."""
    return sorted(name for ct, name in _registry if ct == component_type)


def set_required_base(component_type: str, base: type) -> None:
    """Declare that all plugins of `component_type` must subclass `base`.

    Called once per component type (typically in the base module for that
    component). Applies retroactively — registration before this call is fine
    as long as the class implements the interface.
    """
    with _lock:
        if _frozen:
            raise RegistryFrozenError("set_required_base")
        _required_bases[component_type] = base


def freeze() -> None:
    """Prevent any further registrations.

    Call this at the end of application startup, after all plugin modules
    have been imported. Any attempt to register after this point raises
    RegistryFrozenError.
    """
    global _frozen
    with _lock:
        _frozen = True


def is_frozen() -> bool:
    return _frozen


def validate_against_config(config: Any) -> None:
    """Verify every provider named in config is registered.

    Collects ALL missing providers before raising so the full list is visible
    in one error message. Call this after freeze() and after all plugin modules
    have been imported.

    Args:
        config: A loaded RAGConfig instance.

    Raises:
        MissingProviderError: If any config-referenced provider is unregistered.
    """
    required = _providers_from_config(config)
    missing: list[dict[str, str]] = []

    for component_type, name, config_field in required:
        if not name:
            continue
        key = (component_type, name)
        if key not in _registry:
            missing.append(
                {
                    "component_type": component_type,
                    "name": name,
                    "config_field": config_field,
                }
            )

    if missing:
        raise MissingProviderError(missing)


def reset() -> None:
    """Clear all registrations and unfreeze. FOR TESTING ONLY."""
    global _frozen
    with _lock:
        _registry.clear()
        _required_bases.clear()
        _frozen = False


# ── Private helpers ───────────────────────────────────────────────────────────


def _missing_methods(cls: type, base: type) -> list[str]:
    """Return list of abstract method names that `cls` does not implement."""
    import inspect

    required: list[str] = []
    for name, member in inspect.getmembers(base):
        if getattr(member, "__isabstractmethod__", False):
            impl = getattr(cls, name, None)
            if impl is None or getattr(impl, "__isabstractmethod__", False):
                required.append(name)
    return required


def _providers_from_config(config: Any) -> list[tuple[str, str, str]]:
    """Extract (component_type, provider_name, config_field_path) triples from config.

    Only includes providers that are actually enabled / non-null so we don't
    flag optional components that have been explicitly disabled.
    """
    pairs: list[tuple[str, str, str]] = []

    def add(component_type: str, name: str | None, field: str) -> None:
        if name:
            pairs.append((component_type, name, field))

    # Core pipeline components.
    add("chunking",      config.chunking.strategy.value,               "chunking.strategy")
    add("embedding",     config.embedding.provider.value,              "embedding.provider")
    add("vector_store",  config.storage.vector_store.provider.value,   "storage.vector_store.provider")
    add("document_store",config.storage.document_store.provider.value, "storage.document_store.provider")
    add("retriever",     config.retrieval.strategy.value,              "retrieval.strategy")
    add("llm",           config.generation.provider.value,             "generation.provider")

    # Optional components — only if enabled.
    if config.storage.graph_store:
        add("graph_store", config.storage.graph_store.provider.value, "storage.graph_store.provider")

    if config.augmentation.reranker.enabled:
        add("reranker", config.augmentation.reranker.provider.value, "augmentation.reranker.provider")
        if config.augmentation.reranker.fallback_provider:
            add(
                "reranker",
                config.augmentation.reranker.fallback_provider.value,
                "augmentation.reranker.fallback_provider",
            )

    if config.embedding.fallback and config.embedding.fallback.enabled:
        add("embedding", config.embedding.fallback.provider.value, "embedding.fallback.provider")

    if config.generation.fallback and config.generation.fallback.enabled:
        add("llm", config.generation.fallback.provider.value, "generation.fallback.provider")

    if config.retrieval.strategy.value == "sparse":
        add("sparse_retriever", config.retrieval.sparse.provider.value, "retrieval.sparse.provider")
    elif config.retrieval.strategy.value == "hybrid":
        add("sparse_retriever", config.retrieval.sparse.provider.value, "retrieval.sparse.provider")

    # Agent tools.
    for tool_name in config.agents.tools:
        add("tool", tool_name, f"agents.tools[{tool_name!r}]")

    return pairs
