"""Tests for Bedrock LLM provider."""

import pytest
from unittest.mock import patch, MagicMock

from cli.llm_bedrock import BedrockProvider
from cli.llm_base import LLMProvider, LLMError


class TestBedrockProviderBase:
    """Tests for BedrockProvider base functionality."""

    @patch("cli.llm_bedrock.boto3.client")
    def test_inherits_from_llm_provider(self, mock_boto_client):
        """Test that BedrockProvider inherits from LLMProvider."""
        assert issubclass(BedrockProvider, LLMProvider)

    @patch("cli.llm_bedrock.boto3.client")
    def test_provider_name(self, mock_boto_client):
        """Test provider_name property."""
        provider = BedrockProvider("us-east-1")
        assert provider.provider_name == "bedrock"

    @patch("cli.llm_bedrock.boto3.client")
    def test_model_name(self, mock_boto_client):
        """Test model_name property."""
        provider = BedrockProvider("us-east-1", model_id="anthropic.claude-3-haiku-v1")
        assert provider.model_name == "anthropic.claude-3-haiku-v1"

    @patch("cli.llm_bedrock.boto3.client")
    def test_default_model(self, mock_boto_client):
        """Test default model is set correctly."""
        provider = BedrockProvider("us-east-1")
        assert "claude-sonnet-4-5" in provider.model_name


class TestBedrockProviderAnalyzeComplexity:
    """Tests for BedrockProvider.analyze_complexity method."""

    @patch("cli.llm_bedrock.boto3.client")
    def test_analyze_complexity_success(self, mock_boto_client):
        """Test successful complexity analysis."""
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [{"text": '{"complexity": 5, "explanation": "Medium complexity"}'}]
                }
            },
            "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
        }
        mock_boto_client.return_value = mock_client

        provider = BedrockProvider("us-east-1")
        result = provider.analyze_complexity(
            prompt="Analyze this PR",
            diff_excerpt="diff content",
            stats_json='{"additions": 10}',
            title="Fix bug",
        )

        assert result["complexity"] == 5
        assert result["explanation"] == "Medium complexity"
        assert result["provider"] == "bedrock"
        assert result["tokens"] == 150

    @patch("cli.llm_bedrock.boto3.client")
    def test_analyze_complexity_empty_response(self, mock_boto_client):
        """Test handling of empty LLM response."""
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {"message": {"content": []}},
            "usage": {},
        }
        mock_boto_client.return_value = mock_client

        provider = BedrockProvider("us-east-1")

        with pytest.raises(LLMError, match="Empty response"):
            provider.analyze_complexity(
                prompt="Analyze",
                diff_excerpt="diff",
                stats_json="{}",
                title="Title",
                max_retries=1,
            )

    @patch("cli.llm_bedrock.boto3.client")
    def test_analyze_complexity_invalid_json(self, mock_boto_client):
        """Test handling of invalid JSON response."""
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "not valid json"}]}},
            "usage": {},
        }
        mock_boto_client.return_value = mock_client

        provider = BedrockProvider("us-east-1")

        with pytest.raises(LLMError, match="Failed to parse"):
            provider.analyze_complexity(
                prompt="Analyze",
                diff_excerpt="diff",
                stats_json="{}",
                title="Title",
                max_retries=1,
            )

    @patch("cli.llm_bedrock.boto3.client")
    @patch("cli.llm_bedrock.time.sleep")
    def test_analyze_complexity_retry_on_error(self, mock_sleep, mock_boto_client):
        """Test retry logic on transient errors."""
        mock_client = MagicMock()
        mock_client.converse.side_effect = [
            Exception("Temporary error"),
            {
                "output": {
                    "message": {
                        "content": [{"text": '{"complexity": 3, "explanation": "Low"}'}]
                    }
                },
                "usage": {"inputTokens": 200, "outputTokens": 300, "totalTokens": 500},
            },
        ]
        mock_boto_client.return_value = mock_client

        provider = BedrockProvider("us-east-1")
        result = provider.analyze_complexity(
            prompt="Analyze",
            diff_excerpt="diff",
            stats_json="{}",
            title="Title",
            max_retries=3,
        )

        assert result["complexity"] == 3
        assert mock_client.converse.call_count == 2
        mock_sleep.assert_called()
