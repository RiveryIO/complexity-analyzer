"""Tests for LLM module."""

import pytest
from unittest.mock import patch, MagicMock

from cli.llm import OpenAIProvider, LLMError, create_llm_provider
from cli.llm_base import LLMProvider


class TestOpenAIProviderBase:
    """Tests for OpenAIProvider base functionality."""

    def test_inherits_from_llm_provider(self):
        """Test that OpenAIProvider inherits from LLMProvider."""
        assert issubclass(OpenAIProvider, LLMProvider)

    @patch("cli.llm.OpenAI")
    def test_provider_name(self, mock_openai):
        """Test provider_name property."""
        provider = OpenAIProvider("test-key")
        assert provider.provider_name == "openai"

    @patch("cli.llm.OpenAI")
    def test_model_name(self, mock_openai):
        """Test model_name property."""
        provider = OpenAIProvider("test-key", model="gpt-4")
        assert provider.model_name == "gpt-4"

    @patch("cli.llm.OpenAI")
    def test_model_backward_compat(self, mock_openai):
        """Test model property for backward compatibility."""
        provider = OpenAIProvider("test-key", model="gpt-5.2")
        assert provider.model == "gpt-5.2"

    @patch("cli.llm.OpenAI")
    def test_default_model(self, mock_openai):
        """Test default model is set correctly."""
        provider = OpenAIProvider("test-key")
        assert provider.model_name == "gpt-5.2"


class TestOpenAIProviderAnalyzeComplexity:
    """Tests for OpenAIProvider.analyze_complexity method."""

    @patch("cli.llm.OpenAI")
    def test_analyze_complexity_success(self, mock_openai_class):
        """Test successful complexity analysis."""
        # Set up mock response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content='{"complexity": 5, "explanation": "Medium complexity"}')
            )
        ]
        mock_response.usage = MagicMock(total_tokens=1000)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider("test-key", model="gpt-5.2")
        result = provider.analyze_complexity(
            prompt="Analyze this PR",
            diff_excerpt="diff content",
            stats_json='{"additions": 10}',
            title="Fix bug",
        )

        assert result["complexity"] == 5
        assert result["explanation"] == "Medium complexity"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-5.2"
        assert result["tokens"] == 1000

    @patch("cli.llm.OpenAI")
    def test_analyze_complexity_empty_response(self, mock_openai_class):
        """Test handling of empty LLM response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider("test-key")

        with pytest.raises(LLMError, match="Empty response"):
            provider.analyze_complexity(
                prompt="Analyze",
                diff_excerpt="diff",
                stats_json="{}",
                title="Title",
                max_retries=1,
            )

    @patch("cli.llm.OpenAI")
    def test_analyze_complexity_invalid_json(self, mock_openai_class):
        """Test handling of invalid JSON response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="not valid json"))]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider("test-key")

        with pytest.raises(LLMError, match="Failed to parse"):
            provider.analyze_complexity(
                prompt="Analyze",
                diff_excerpt="diff",
                stats_json="{}",
                title="Title",
                max_retries=1,
            )

    @patch("cli.llm.OpenAI")
    @patch("cli.llm.time.sleep")
    def test_analyze_complexity_retry_on_error(self, mock_sleep, mock_openai_class):
        """Test retry logic on transient errors."""
        # First call fails, second succeeds
        mock_response_success = MagicMock()
        mock_response_success.choices = [
            MagicMock(message=MagicMock(content='{"complexity": 3, "explanation": "Low"}'))
        ]
        mock_response_success.usage = MagicMock(total_tokens=500)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            Exception("Temporary error"),
            mock_response_success,
        ]
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider("test-key")
        result = provider.analyze_complexity(
            prompt="Analyze",
            diff_excerpt="diff",
            stats_json="{}",
            title="Title",
            max_retries=3,
        )

        assert result["complexity"] == 3
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called()

    @patch("cli.llm.OpenAI")
    def test_analyze_complexity_all_retries_fail(self, mock_openai_class):
        """Test behavior when all retries fail."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Persistent error")
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider("test-key")

        with pytest.raises(LLMError, match="after 2 attempts"):
            provider.analyze_complexity(
                prompt="Analyze",
                diff_excerpt="diff",
                stats_json="{}",
                title="Title",
                max_retries=2,
            )

    @patch("cli.llm.OpenAI")
    def test_analyze_complexity_no_usage(self, mock_openai_class):
        """Test handling when usage info is missing."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"complexity": 7, "explanation": "High"}'))
        ]
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        provider = OpenAIProvider("test-key")
        result = provider.analyze_complexity(
            prompt="Analyze",
            diff_excerpt="diff",
            stats_json="{}",
            title="Title",
        )

        assert result["complexity"] == 7
        assert result["tokens"] is None


class TestCreateLLMProvider:
    """Tests for create_llm_provider factory."""

    def test_create_openai_provider(self):
        """Test creating OpenAI provider."""
        provider = create_llm_provider("openai", openai_key="test-key")
        assert provider.provider_name == "openai"
        assert provider.model_name == "gpt-5.2"

    def test_create_openai_provider_requires_key(self):
        """Test that OpenAI provider requires API key."""
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            create_llm_provider("openai")

    @patch("cli.llm_bedrock.boto3.client")
    def test_create_bedrock_provider(self, mock_boto_client):
        """Test creating Bedrock provider."""
        provider = create_llm_provider("bedrock")
        assert provider.provider_name == "bedrock"
        assert "claude" in provider.model_name.lower()

    @patch("cli.llm_bedrock.boto3.client")
    def test_create_bedrock_provider_with_overrides(self, mock_boto_client):
        """Test that bedrock_model and bedrock_region overrides work."""
        provider = create_llm_provider(
            "bedrock",
            bedrock_model="anthropic.claude-3-haiku-v1",
            bedrock_region="eu-west-1",
        )
        assert provider.model_name == "anthropic.claude-3-haiku-v1"
        assert provider._region == "eu-west-1"

    def test_create_anthropic_provider(self):
        """Test creating Anthropic provider."""
        provider = create_llm_provider("anthropic", anthropic_key="test-key")
        assert provider.provider_name == "anthropic"
        assert "claude" in provider.model_name.lower()

    def test_create_anthropic_provider_requires_key(self):
        """Test that Anthropic provider requires API key."""
        with pytest.raises(ValueError, match="Anthropic API key is required"):
            create_llm_provider("anthropic")

    def test_unknown_provider_raises(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            create_llm_provider("unknown")


class TestLLMError:
    """Tests for LLMError exception."""

    def test_llm_error_message(self):
        """Test LLMError stores message correctly."""
        error = LLMError("Something went wrong")
        assert str(error) == "Something went wrong"

    def test_llm_error_is_exception(self):
        """Test LLMError is an Exception."""
        assert issubclass(LLMError, Exception)
