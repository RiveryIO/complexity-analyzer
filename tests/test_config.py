"""Tests for config module."""

import os
import pytest
from unittest.mock import patch
from cli.config import (
    validate_owner_repo,
    validate_pr_number,
    get_github_tokens,
    get_bedrock_config,
    get_anthropic_api_key,
)
from cli.config_types import AnalysisConfig, BatchConfig, OutputConfig


def test_validate_owner_repo_valid():
    """Test valid owner/repo names."""
    validate_owner_repo("owner", "repo")
    validate_owner_repo("owner-name", "repo_name")
    validate_owner_repo("owner.name", "repo-123")


def test_validate_owner_repo_invalid():
    """Test invalid owner/repo names."""
    with pytest.raises(ValueError):
        validate_owner_repo("owner/repo", "repo")
    with pytest.raises(ValueError):
        validate_owner_repo("owner", "repo@name")


def test_validate_pr_number():
    """Test PR number validation."""
    validate_pr_number(1)
    validate_pr_number(123)
    with pytest.raises(ValueError):
        validate_pr_number(0)
    with pytest.raises(ValueError):
        validate_pr_number(-1)


# get_github_tokens tests


class TestGetGitHubTokens:
    """Tests for the get_github_tokens function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_no_tokens_returns_empty(self):
        """Test that empty list is returned when no tokens are set."""
        tokens = get_github_tokens()
        assert tokens == []

    @patch.dict(os.environ, {"GH_TOKEN": "single_token"}, clear=True)
    def test_single_token_from_gh_token(self):
        """Test getting single token from GH_TOKEN."""
        tokens = get_github_tokens()
        assert tokens == ["single_token"]

    @patch.dict(os.environ, {"GITHUB_TOKEN": "single_token"}, clear=True)
    def test_single_token_from_github_token(self):
        """Test getting single token from GITHUB_TOKEN."""
        tokens = get_github_tokens()
        assert tokens == ["single_token"]

    @patch.dict(os.environ, {"GH_TOKENS": "token1,token2,token3"}, clear=True)
    def test_multiple_tokens_comma_separated(self):
        """Test getting multiple tokens from GH_TOKENS (comma-separated)."""
        tokens = get_github_tokens()
        assert tokens == ["token1", "token2", "token3"]

    @patch.dict(os.environ, {"GH_TOKENS": "token1\ntoken2\ntoken3"}, clear=True)
    def test_multiple_tokens_newline_separated(self):
        """Test getting multiple tokens from GH_TOKENS (newline-separated)."""
        tokens = get_github_tokens()
        assert tokens == ["token1", "token2", "token3"]

    @patch.dict(os.environ, {"GH_TOKENS": "token1, token2 , token3"}, clear=True)
    def test_tokens_are_stripped(self):
        """Test that tokens are stripped of whitespace."""
        tokens = get_github_tokens()
        assert tokens == ["token1", "token2", "token3"]

    @patch.dict(os.environ, {"GH_TOKENS": "token1,,token2,,,token3"}, clear=True)
    def test_empty_tokens_filtered(self):
        """Test that empty tokens are filtered out."""
        tokens = get_github_tokens()
        assert tokens == ["token1", "token2", "token3"]

    @patch.dict(os.environ, {"GITHUB_TOKENS": "token1,token2"}, clear=True)
    def test_multiple_tokens_from_github_tokens(self):
        """Test getting multiple tokens from GITHUB_TOKENS."""
        tokens = get_github_tokens()
        assert tokens == ["token1", "token2"]

    @patch.dict(os.environ, {"GH_TOKENS": "multi1,multi2", "GH_TOKEN": "single"}, clear=True)
    def test_gh_tokens_takes_precedence_over_gh_token(self):
        """Test that GH_TOKENS takes precedence over GH_TOKEN."""
        tokens = get_github_tokens()
        assert tokens == ["multi1", "multi2"]

    @patch.dict(os.environ, {"GH_TOKENS": "", "GH_TOKEN": "fallback"}, clear=True)
    def test_falls_back_to_single_token_if_multi_empty(self):
        """Test fallback to single token if multi-token env var is empty."""
        tokens = get_github_tokens()
        assert tokens == ["fallback"]


# get_bedrock_config tests


class TestGetBedrockConfig:
    """Tests for get_bedrock_config function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_region_and_model(self):
        """Test default region and model when no env vars set."""
        region, model_id = get_bedrock_config()
        assert region == "us-east-1"
        assert "claude-sonnet-4-5" in model_id

    @patch.dict(os.environ, {"AWS_REGION": "us-west-2"}, clear=True)
    def test_uses_aws_region(self):
        """Test that AWS_REGION is used."""
        region, _ = get_bedrock_config()
        assert region == "us-west-2"

    @patch.dict(os.environ, {"BEDROCK_REGION": "eu-west-1"}, clear=True)
    def test_bedrock_region_takes_precedence(self):
        """Test that BEDROCK_REGION takes precedence over AWS_REGION."""
        region, _ = get_bedrock_config()
        assert region == "eu-west-1"

    @patch.dict(os.environ, {"BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-v1"}, clear=True)
    def test_bedrock_model_id(self):
        """Test that BEDROCK_MODEL_ID is used."""
        _, model_id = get_bedrock_config()
        assert model_id == "anthropic.claude-3-haiku-v1"


# get_anthropic_api_key tests


class TestGetAnthropicApiKey:
    """Tests for get_anthropic_api_key function."""

    @patch.dict(os.environ, {}, clear=True)
    def test_no_key_returns_none(self):
        """Test that None is returned when no key is set."""
        assert get_anthropic_api_key() is None

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_anthropic_api_key(self):
        """Test getting key from ANTHROPIC_API_KEY."""
        assert get_anthropic_api_key() == "sk-ant-test"

    @patch.dict(os.environ, {"ANTROPIC_API_KEY": "sk-ant-typo"}, clear=True)
    def test_antropic_typo_fallback(self):
        """Test that ANTROPIC_API_KEY (typo) is supported."""
        assert get_anthropic_api_key() == "sk-ant-typo"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "correct", "ANTROPIC_API_KEY": "typo"}, clear=True)
    def test_anthropic_takes_precedence_over_typo(self):
        """Test that ANTHROPIC_API_KEY takes precedence over ANTROPIC_API_KEY."""
        assert get_anthropic_api_key() == "correct"


# AnalysisConfig validation tests


class TestAnalysisConfigValidation:
    """Tests for AnalysisConfig validation."""

    def test_valid_config(self):
        """Test that valid config is accepted."""
        config = AnalysisConfig(
            model="gpt-4",
            timeout=30.0,
            max_tokens=1000,
            hunks_per_file=5,
            sleep_seconds=0.5,
        )
        assert config.model == "gpt-4"
        assert config.timeout == 30.0

    def test_timeout_must_be_positive(self):
        """Test that timeout must be positive."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            AnalysisConfig(timeout=-10.0)
        with pytest.raises(ValueError, match="timeout must be positive"):
            AnalysisConfig(timeout=0.0)

    def test_max_tokens_must_be_positive(self):
        """Test that max_tokens must be positive."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            AnalysisConfig(max_tokens=0)
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            AnalysisConfig(max_tokens=-100)

    def test_hunks_per_file_must_be_positive(self):
        """Test that hunks_per_file must be positive."""
        with pytest.raises(ValueError, match="hunks_per_file must be positive"):
            AnalysisConfig(hunks_per_file=0)
        with pytest.raises(ValueError, match="hunks_per_file must be positive"):
            AnalysisConfig(hunks_per_file=-5)

    def test_sleep_seconds_cannot_be_negative(self):
        """Test that sleep_seconds cannot be negative."""
        with pytest.raises(ValueError, match="sleep_seconds cannot be negative"):
            AnalysisConfig(sleep_seconds=-1.0)
        # Zero is allowed
        config = AnalysisConfig(sleep_seconds=0.0)
        assert config.sleep_seconds == 0.0

    def test_model_cannot_be_empty(self):
        """Test that model cannot be empty."""
        with pytest.raises(ValueError, match="model cannot be empty"):
            AnalysisConfig(model="")
        with pytest.raises(ValueError, match="model cannot be empty"):
            AnalysisConfig(model="   ")


# BatchConfig validation tests


class TestBatchConfigValidation:
    """Tests for BatchConfig validation."""

    def test_valid_config(self):
        """Test that valid config is accepted."""
        config = BatchConfig(workers=4, label_prs=True, label_prefix="complexity:")
        assert config.workers == 4

    def test_workers_must_be_at_least_one(self):
        """Test that workers must be >= 1."""
        with pytest.raises(ValueError, match="workers must be >= 1"):
            BatchConfig(workers=0)
        with pytest.raises(ValueError, match="workers must be >= 1"):
            BatchConfig(workers=-1)

    def test_label_prefix_required_when_label_prs_true(self):
        """Test that label_prefix cannot be empty when label_prs is True."""
        with pytest.raises(ValueError, match="label_prefix cannot be empty when label_prs is True"):
            BatchConfig(label_prs=True, label_prefix="")
        # Empty prefix is allowed when label_prs is False
        config = BatchConfig(label_prs=False, label_prefix="")
        assert config.label_prefix == ""


# OutputConfig validation tests


class TestOutputConfigValidation:
    """Tests for OutputConfig validation."""

    def test_valid_json_format(self):
        """Test that json format is accepted."""
        config = OutputConfig(format="json")
        assert config.format == "json"

    def test_valid_markdown_format(self):
        """Test that markdown format is accepted."""
        config = OutputConfig(format="markdown")
        assert config.format == "markdown"

    def test_invalid_format_rejected(self):
        """Test that invalid formats are rejected."""
        with pytest.raises(ValueError, match="format must be 'json' or 'markdown'"):
            OutputConfig(format="xml")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="format must be 'json' or 'markdown'"):
            OutputConfig(format="MARKDOWN")  # type: ignore[arg-type]
