"""Tests for Anthropic LLM provider."""

import pytest
from unittest.mock import patch, MagicMock

from cli.llm_anthropic import AnthropicProvider
from cli.llm_base import LLMProvider, LLMError


class TestAnthropicProviderBase:
    """Tests for AnthropicProvider base functionality."""

    @patch("cli.llm_anthropic.anthropic.Anthropic")
    def test_inherits_from_llm_provider(self, mock_anthropic):
        """Test that AnthropicProvider inherits from LLMProvider."""
        assert issubclass(AnthropicProvider, LLMProvider)

    @patch("cli.llm_anthropic.anthropic.Anthropic")
    def test_provider_name(self, mock_anthropic):
        """Test provider_name property."""
        provider = AnthropicProvider("test-key")
        assert provider.provider_name == "anthropic"

    @patch("cli.llm_anthropic.anthropic.Anthropic")
    def test_model_name(self, mock_anthropic):
        """Test model_name property."""
        provider = AnthropicProvider("test-key", model="claude-3-5-sonnet-20241022")
        assert provider.model_name == "claude-3-5-sonnet-20241022"

    @patch("cli.llm_anthropic.anthropic.Anthropic")
    def test_default_model(self, mock_anthropic):
        """Test default model is set correctly."""
        provider = AnthropicProvider("test-key")
        assert "claude-sonnet-4-5" in provider.model_name


class TestAnthropicProviderAnalyzeComplexity:
    """Tests for AnthropicProvider.analyze_complexity method."""

    @patch("cli.llm_anthropic.anthropic.Anthropic")
    def test_analyze_complexity_success(self, mock_anthropic_class):
        """Test successful complexity analysis."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"complexity": 5, "explanation": "Medium complexity"}')]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicProvider("test-key")
        result = provider.analyze_complexity(
            prompt="Analyze this PR",
            diff_excerpt="diff content",
            stats_json='{"additions": 10}',
            title="Fix bug",
        )

        assert result["complexity"] == 5
        assert result["explanation"] == "Medium complexity"
        assert result["provider"] == "anthropic"
        assert result["tokens"] == 150
