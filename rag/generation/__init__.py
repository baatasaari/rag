"""
LBG RAG — Generation Layer

Public surface:
  GeneratedAnswer  — canonical answer record produced by any LLM adapter
  LLMAdapter       — structural Protocol every adapter must satisfy
  VertexAIAdapter  — Gemini via google-cloud-aiplatform (lazy import)
  AnthropicAdapter — Claude via anthropic SDK (lazy import)
  OpenAIAdapter    — OpenAI / Azure OpenAI via openai SDK (lazy import)
  CachedGenerator  — wraps an LLMAdapter + SemanticCache for cache-first generation
  GenerationEngine — orchestrator: cache → generate → fallback → stream
"""

from rag.generation.protocols import GeneratedAnswer, LLMAdapter
from rag.generation.adapters.vertex import VertexAIAdapter
from rag.generation.adapters.anthropic import AnthropicAdapter
from rag.generation.adapters.openai import OpenAIAdapter
from rag.generation.cache import CachedGenerator
from rag.generation.engine import GenerationEngine

__all__ = [
    "GeneratedAnswer",
    "LLMAdapter",
    "VertexAIAdapter",
    "AnthropicAdapter",
    "OpenAIAdapter",
    "CachedGenerator",
    "GenerationEngine",
]
