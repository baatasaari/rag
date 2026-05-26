"""
Shared pytest fixtures for the LBG RAG Platform test suite.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rag.core import config as config_module
from rag.core import registry as registry_module

# Root of the repo — used to locate the real config/ directory.
REPO_ROOT = Path(__file__).parent.parent
CONFIG_DIR = REPO_ROOT / "config"


@pytest.fixture(autouse=True)
def reset_config_singleton():
    """Reset config singleton before and after every test."""
    config_module._config = None
    yield
    config_module._config = None


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry state before and after every test."""
    registry_module.reset()
    yield
    registry_module.reset()


@pytest.fixture()
def real_config_dir() -> Path:
    """Return the real config/ directory from the repo."""
    return CONFIG_DIR


@pytest.fixture()
def minimal_env(monkeypatch) -> None:
    """Set the minimum environment variables required to load the dev config."""
    vars_ = {
        "GCP_PROJECT_ID": "lbg-rag-test",
        "ALLOYDB_CONNECTION": "postgresql+asyncpg://user:pass@localhost/rag",
        "REDIS_URL": "redis://localhost:6379/0",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "test",
        "COHERE_API_KEY": "test-key",
        "CONFLUENCE_URL": "https://lbg.atlassian.net",
        "SHAREPOINT_TENANT_ID": "test-tenant-id",
        "VERTEX_SEARCH_DATA_STORE_ID": "test-data-store",
    }
    for k, v in vars_.items():
        monkeypatch.setenv(k, v)
