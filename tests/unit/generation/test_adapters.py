"""
Tests for LLM adapters — VertexAIAdapter, AnthropicAdapter, OpenAIAdapter.

All external SDK calls are mocked so no API keys or network access is needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from rag.core.schemas import GenerationConfig, LLMProvider
from rag.generation.adapters.anthropic import AnthropicAdapter
from rag.generation.adapters.openai import OpenAIAdapter
from rag.generation.adapters.vertex import VertexAIAdapter
from rag.generation.protocols import GeneratedAnswer


# ── helpers ───────────────────────────────────────────────────────────────────

def _vertex_cfg() -> GenerationConfig:
    return GenerationConfig(
        provider=LLMProvider.VERTEX_AI,
        model="gemini-2.0-flash-001",
        location="europe-west2",
        project_id="lbg-test",
    )


def _anthropic_cfg() -> GenerationConfig:
    return GenerationConfig(
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        api_key=SecretStr("sk-test"),
    )


def _openai_cfg(provider=LLMProvider.OPENAI) -> GenerationConfig:
    return GenerationConfig(
        provider=provider,
        model="gpt-4o",
        api_key=SecretStr("sk-test"),
    )


# ── VertexAIAdapter ───────────────────────────────────────────────────────────

class TestVertexAIAdapterProperties:
    def test_provider_name(self):
        assert VertexAIAdapter(_vertex_cfg()).provider_name == "vertex_ai"

    def test_model_name(self):
        assert VertexAIAdapter(_vertex_cfg()).model_name == "gemini-2.0-flash-001"


class TestVertexAIAdapterGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_generated_answer(self):
        adapter = VertexAIAdapter(_vertex_cfg())
        mock_response = MagicMock()
        mock_response.text = "The policy requires [1] annual review."
        mock_response.usage_metadata.prompt_token_count = 120
        mock_response.usage_metadata.candidates_token_count = 40

        mock_model_cls = MagicMock()
        mock_model_instance = MagicMock()
        mock_model_instance.generate_content_async = AsyncMock(return_value=mock_response)
        mock_model_cls.return_value = mock_model_instance

        with patch.dict("sys.modules", {
            "vertexai": MagicMock(),
            "vertexai.generative_models": MagicMock(
                GenerativeModel=mock_model_cls,
                GenerationConfig=MagicMock(return_value=MagicMock()),
            ),
        }):
            result = await adapter.generate("sys", "user msg")

        assert isinstance(result, GeneratedAnswer)
        assert result.provider == "vertex_ai"
        assert result.tokens_in == 120
        assert result.tokens_out == 40
        assert "annual review" in result.answer

    @pytest.mark.asyncio
    async def test_import_error_raises_runtime_error(self):
        adapter = VertexAIAdapter(_vertex_cfg())
        with patch.dict("sys.modules", {"vertexai": None, "vertexai.generative_models": None}):
            with pytest.raises((RuntimeError, ImportError)):
                await adapter.generate("sys", "user msg")


class TestVertexAIAdapterStream:
    @pytest.mark.asyncio
    async def test_stream_yields_text_chunks(self):
        adapter = VertexAIAdapter(_vertex_cfg())

        async def fake_stream(*args, **kwargs):
            class FakeChunk:
                text = "hello "
            yield FakeChunk()
            class FakeChunk2:
                text = "world"
            yield FakeChunk2()

        mock_model_instance = MagicMock()
        mock_model_instance.generate_content_async = AsyncMock(return_value=fake_stream())
        mock_model_cls = MagicMock(return_value=mock_model_instance)

        with patch.dict("sys.modules", {
            "vertexai": MagicMock(),
            "vertexai.generative_models": MagicMock(
                GenerativeModel=mock_model_cls,
                GenerationConfig=MagicMock(return_value=MagicMock()),
            ),
        }):
            tokens = [t async for t in adapter.stream("sys", "user")]

        assert "hello " in tokens
        assert "world" in tokens


# ── AnthropicAdapter ──────────────────────────────────────────────────────────

class TestAnthropicAdapterProperties:
    def test_provider_name(self):
        assert AnthropicAdapter(_anthropic_cfg()).provider_name == "anthropic"

    def test_model_name(self):
        assert AnthropicAdapter(_anthropic_cfg()).model_name == "claude-sonnet-4-6"

    def test_missing_api_key_raises(self):
        cfg = GenerationConfig(provider=LLMProvider.ANTHROPIC, model="claude-x")
        with pytest.raises(ValueError, match="api_key"):
            AnthropicAdapter(cfg)


class TestAnthropicAdapterGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_generated_answer(self):
        adapter = AnthropicAdapter(_anthropic_cfg())
        mock_content = MagicMock()
        mock_content.text = "The answer is [1]."
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_response.usage.input_tokens = 80
        mock_response.usage.output_tokens = 20

        mock_client = MagicMock()
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        mock_anthropic = MagicMock()
        mock_anthropic.AsyncAnthropic = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = await adapter.generate("sys", "user msg")

        assert result.provider == "anthropic"
        assert result.tokens_in == 80
        assert result.tokens_out == 20
        assert result.citations_used == [1]

    @pytest.mark.asyncio
    async def test_import_error_raises_runtime_error(self):
        adapter = AnthropicAdapter(_anthropic_cfg())
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises((RuntimeError, ImportError)):
                await adapter.generate("sys", "user msg")


# ── OpenAIAdapter ─────────────────────────────────────────────────────────────

class TestOpenAIAdapterProperties:
    def test_provider_name_openai(self):
        assert OpenAIAdapter(_openai_cfg()).provider_name == "openai"

    def test_provider_name_azure(self):
        assert OpenAIAdapter(_openai_cfg(LLMProvider.AZURE_OPENAI)).provider_name == "azure_openai"

    def test_model_name(self):
        assert OpenAIAdapter(_openai_cfg()).model_name == "gpt-4o"

    def test_missing_api_key_raises_for_openai(self):
        cfg = GenerationConfig(provider=LLMProvider.OPENAI, model="gpt-4o")
        with pytest.raises(ValueError, match="api_key"):
            OpenAIAdapter(cfg)


class TestOpenAIAdapterGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_generated_answer(self):
        adapter = OpenAIAdapter(_openai_cfg())

        mock_choice = MagicMock()
        mock_choice.message.content = "Policy requires compliance [2]."
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 60
        mock_usage.completion_tokens = 15
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage

        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_openai = MagicMock()
        mock_openai.AsyncOpenAI = MagicMock(return_value=mock_client)
        mock_openai.AsyncAzureOpenAI = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = await adapter.generate("sys", "user msg")

        assert result.provider == "openai"
        assert result.tokens_in == 60
        assert result.tokens_out == 15
        assert result.citations_used == [2]

    @pytest.mark.asyncio
    async def test_import_error_raises_runtime_error(self):
        adapter = OpenAIAdapter(_openai_cfg())
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises((RuntimeError, ImportError)):
                await adapter.generate("sys", "user msg")
