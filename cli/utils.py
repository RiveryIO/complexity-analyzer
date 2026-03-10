"""Shared utilities for the CLI."""

import re
from typing import Dict, List, Optional, Tuple

from .constants import GITHUB_API_VERSION, TOKEN_VISIBLE_CHARS

# Regex to parse PR URLs
_GITHUB_PR_RE = re.compile(
    r"https?://github\.com/([^/\s]+)/([^/\s]+)/pull/(\d+)"
)
_BITBUCKET_PR_RE = re.compile(
    r"https?://bitbucket\.org/([^/\s]+)/([^/\s]+)/pull-requests/(\d+)"
)

# Keep legacy name for backward compat in tests
_OWNER_REPO_RE = _GITHUB_PR_RE


def detect_pr_provider(url: str) -> str:
    """Detect whether a PR URL is from GitHub or Bitbucket.

    Returns:
        "github" or "bitbucket"

    Raises:
        ValueError: If URL is not a recognized PR URL
    """
    url = url.strip()
    if _GITHUB_PR_RE.match(url):
        return "github"
    if _BITBUCKET_PR_RE.match(url):
        return "bitbucket"
    raise ValueError(f"Unrecognized PR URL (not GitHub or Bitbucket): {url}")


def parse_pr_url(url: str) -> Tuple[str, str, int]:
    """
    Parse owner/workspace, repo, and PR number from a PR URL.

    Args:
        url: PR URL from either platform:
            - GitHub:    https://github.com/owner/repo/pull/123
            - Bitbucket: https://bitbucket.org/workspace/repo/pull-requests/123

    Returns:
        Tuple of (owner_or_workspace, repo, pr_number)

    Raises:
        ValueError: If URL format is invalid
    """
    url = url.strip()
    m = _GITHUB_PR_RE.match(url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    m = _BITBUCKET_PR_RE.match(url)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    raise ValueError(f"Invalid PR URL: {url}")


def build_github_headers(token: Optional[str] = None) -> Dict[str, str]:
    """
    Build headers for GitHub API requests.

    Args:
        token: Optional GitHub token for authentication

    Returns:
        Dict of headers for HTTP requests
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def build_github_diff_headers(token: Optional[str] = None) -> Dict[str, str]:
    """
    Build headers for GitHub API diff requests.

    Args:
        token: Optional GitHub token for authentication

    Returns:
        Dict of headers for diff requests
    """
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def setup_github_tokens(
    cli_tokens: Optional[str] = None,
    env_tokens_getter: Optional[callable] = None,
) -> Tuple[List[str], Optional[str]]:
    """
    Set up GitHub tokens from CLI argument or environment.

    Args:
        cli_tokens: Comma-separated tokens from CLI argument
        env_tokens_getter: Function to get tokens from environment (defaults to config.get_github_tokens)

    Returns:
        Tuple of (token_list, single_token) where single_token is the first token or None
    """
    from .config import get_github_tokens

    getter = env_tokens_getter or get_github_tokens

    token_list: List[str] = []
    if cli_tokens:
        # Parse comma-separated tokens from CLI
        token_list = [t.strip() for t in cli_tokens.split(",") if t.strip()]
    else:
        # Fall back to environment variables
        token_list = getter()

    single_token = token_list[0] if token_list else None
    return token_list, single_token


def redact_token(token: str, visible_chars: int = TOKEN_VISIBLE_CHARS) -> str:
    """
    Redact a token for display, showing only first few characters.

    Args:
        token: The token to redact
        visible_chars: Number of characters to show (default: 4)

    Returns:
        Redacted string like "ghp_..." or "****"
    """
    if not token:
        return "***"
    if len(token) <= visible_chars:
        return "*" * len(token)
    return token[:visible_chars] + "..."
