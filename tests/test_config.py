"""Tests for config module."""

import os
import pytest
from unittest.mock import patch
from cli.config import validate_owner_repo, validate_pr_number, get_github_tokens


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
