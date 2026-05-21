"""Bitbucket API client for fetching PR diffs, metadata, and posting comments."""

import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from .bitbucket_identity import resolve_bitbucket_username
from .constants import (
    BITBUCKET_API_BASE_URL,
    BITBUCKET_PER_PAGE,
    DEFAULT_SLEEP_SECONDS,
    DEFAULT_TIMEOUT,
)

COMPLEXITY_MARKER = "<!-- [complexity-analyzer] -->"


class BitbucketAPIError(Exception):
    """Bitbucket API error."""

    def __init__(self, status_code: int, message: str, url: str):
        self.status_code = status_code
        self.message = message
        self.url = url
        super().__init__(f"Bitbucket API error {status_code} for {url}: {message}")


def _build_auth(email: str, token: str) -> httpx.BasicAuth:
    return httpx.BasicAuth(username=email, password=token)


def _count_diff_lines(diff_text: str) -> Tuple[int, int]:
    """Count additions and deletions from a unified diff."""
    added = 0
    deleted = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            deleted += 1
    return added, deleted


def fetch_bb_pr_diff(
    workspace: str,
    repo: str,
    pr_id: int,
    email: str,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Fetch PR diff from Bitbucket as unified diff text."""
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo}/pullrequests/{pr_id}/diff"
    auth = _build_auth(email, token)

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, auth=auth)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url)
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to fetch BB PR diff: {e}")


def fetch_bb_pr_metadata(
    workspace: str,
    repo: str,
    pr_id: int,
    email: str,
    token: str,
    diff_text: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Fetch PR metadata from Bitbucket, normalized to GitHub-compatible dict.

    If diff_text is provided, additions/deletions are counted from it
    instead of making a separate diff request.
    """
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo}/pullrequests/{pr_id}"
    auth = _build_auth(email, token)

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, auth=auth)
            response.raise_for_status()
            raw = response.json()
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url)
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to fetch BB PR metadata: {e}")

    additions, deletions = 0, 0
    if diff_text is not None:
        additions, deletions = _count_diff_lines(diff_text)

    author = raw.get("author") or {}
    # Resolve username via identity mapping to ensure consistency with team mapping
    # Maps Bitbucket display names (e.g. "Or Hasson") to usernames (e.g. "orhss")
    username = resolve_bitbucket_username(author)

    merged_at = ""
    if raw.get("state") == "MERGED":
        merged_at = raw.get("updated_on") or ""

    # Best-effort: pull ready_for_review_at from activity log if PR was ever a draft.
    ready_for_review_at: Optional[str] = None
    if not raw.get("draft", False):
        try:
            ready_for_review_at = fetch_bb_ready_for_review_at(
                workspace, repo, pr_id, email, token, timeout
            )
        except Exception:
            ready_for_review_at = None

    return {
        "title": raw.get("title") or "",
        "user": {"login": username},
        "created_at": raw.get("created_on") or "",
        "merged_at": merged_at,
        "ready_for_review_at": ready_for_review_at,
        "additions": additions,
        "deletions": deletions,
        "changed_files": 0,
        "files": [],
        "_bb_raw": raw,
    }


def fetch_bb_ready_for_review_at(
    workspace: str,
    repo: str,
    pr_id: int,
    email: str,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """Return ISO timestamp when a draft Bitbucket PR became ready for review, else None.

    Scans /pullrequests/{id}/activity in two ways:
    1. Look for an update entry whose `changes.draft` transitions True → False.
    2. Fallback: if any earlier update has `draft == True`, treat the first
       subsequent `draft == False` update as the ready-for-review moment.
    Returns None if no such transition exists.
    """
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo}/pullrequests/{pr_id}/activity"
    auth = _build_auth(email, token)
    direct_hits: List[str] = []
    updates: List[Tuple[str, Optional[bool]]] = []  # (date, draft_state) in fetched order
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            while url:
                resp = client.get(url, auth=auth)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                payload = resp.json()
                for entry in payload.get("values", []):
                    update = entry.get("update") or {}
                    if not update:
                        continue
                    changes = update.get("changes") or {}
                    draft_change = changes.get("draft") or {}
                    old = str(draft_change.get("old", "")).lower()
                    new = str(draft_change.get("new", "")).lower()
                    ts = update.get("date") or ""
                    if old == "true" and new == "false" and ts:
                        direct_hits.append(ts)
                    draft_state = update.get("draft")
                    if isinstance(draft_state, bool) and ts:
                        updates.append((ts, draft_state))
                url = payload.get("next")
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url or "")
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to fetch BB PR activity: {e}")

    if direct_hits:
        return max(direct_hits)

    # Fallback: order chronologically, find first False after a True.
    updates.sort()  # ascending by date
    saw_draft = False
    for ts, is_draft in updates:
        if is_draft:
            saw_draft = True
        elif saw_draft and not is_draft:
            return ts
    return None


def fetch_bb_pr(
    workspace: str,
    repo: str,
    pr_id: int,
    email: str,
    token: str,
    sleep_s: float = DEFAULT_SLEEP_SECONDS,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[str, Dict[str, Any]]:
    """Fetch both diff and metadata for a Bitbucket PR."""
    diff_text = fetch_bb_pr_diff(workspace, repo, pr_id, email, token, timeout)
    time.sleep(sleep_s)
    metadata = fetch_bb_pr_metadata(
        workspace, repo, pr_id, email, token, diff_text=diff_text, timeout=timeout
    )
    return diff_text, metadata


def list_bb_project_repos(
    workspace: str,
    project_uuid: str,
    email: str,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """List all repositories in a Bitbucket project.

    Args:
        workspace: Bitbucket workspace slug (e.g. "boomii")
        project_uuid: Project UUID including braces (e.g. "{4f41797b-...}")
        email: Bitbucket email for auth
        token: Bitbucket API token

    Returns:
        List of "workspace/repo-slug" strings
    """
    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}"
    auth = _build_auth(email, token)
    repos: List[str] = []
    page = 1

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            while True:
                response = client.get(
                    url,
                    auth=auth,
                    params={
                        "q": f'project.uuid="{project_uuid}"',
                        "pagelen": BITBUCKET_PER_PAGE,
                        "page": page,
                        "fields": "values.full_name,values.slug,size,next",
                    },
                )
                response.raise_for_status()
                data = response.json()

                for repo_obj in data.get("values", []):
                    full_name = repo_obj.get("full_name", "")
                    if full_name:
                        repos.append(full_name)

                if progress_callback:
                    progress_callback(f"Found {len(repos)} repos in project...")

                if not data.get("next"):
                    break
                page += 1
                time.sleep(0.3)

        return repos
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url)
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to list BB project repos: {e}")


def search_bb_merged_prs(
    workspace: str,
    repo: str,
    since: datetime,
    until: datetime,
    email: str,
    token: str,
    sleep_s: float = DEFAULT_SLEEP_SECONDS,
    timeout: float = DEFAULT_TIMEOUT,
    on_pr_found: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[str]:
    """Search for merged PRs in a Bitbucket repo within a date range.

    Returns:
        List of PR URLs (e.g. "https://bitbucket.org/boomii/repo/pull-requests/41")
    """
    since_str = since.strftime("%Y-%m-%dT00:00:00+00:00")
    until_str = until.strftime("%Y-%m-%dT23:59:59+00:00")

    url = f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo}/pullrequests"
    auth = _build_auth(email, token)
    pr_urls: List[str] = []
    page = 1

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            while True:
                response = client.get(
                    url,
                    auth=auth,
                    params={
                        "q": (
                            f'state="MERGED"'
                            f" AND updated_on >= {since_str}"
                            f" AND updated_on <= {until_str}"
                        ),
                        "sort": "-updated_on",
                        "pagelen": BITBUCKET_PER_PAGE,
                        "page": page,
                    },
                )
                response.raise_for_status()
                data = response.json()

                values = data.get("values", [])
                if not values:
                    break

                for pr in values:
                    if pr.get("state") != "MERGED":
                        continue
                    html_href = (pr.get("links") or {}).get("html", {}).get("href", "")
                    if html_href:
                        pr_urls.append(html_href)
                        if on_pr_found:
                            try:
                                on_pr_found(html_href)
                            except Exception:
                                pass

                if progress_callback:
                    progress_callback(f"Found {len(pr_urls)} merged PRs in {workspace}/{repo}...")

                if not data.get("next"):
                    break
                page += 1
                time.sleep(sleep_s)

        return pr_urls
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url)
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to search BB merged PRs: {e}")


def add_bb_pr_comment(
    workspace: str,
    repo: str,
    pr_id: int,
    complexity: int,
    explanation: str,
    email: str,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> int:
    """Post a complexity analysis comment on a Bitbucket PR.

    Returns:
        The comment ID
    """
    body = (
        f"{COMPLEXITY_MARKER}\n"
        f"## Complexity Analysis\n\n"
        f"**Score:** {complexity}/10\n\n"
        f"{explanation.strip()}\n\n"
        f"---\n"
        f"*Tagged by [complexity-analyzer]"
        f"(https://github.com/RiveryIO/complexity-analyzer)*"
    )

    url = (
        f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo}"
        f"/pullrequests/{pr_id}/comments"
    )
    auth = _build_auth(email, token)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, auth=auth, json={"content": {"raw": body}})
            response.raise_for_status()
            data = response.json()
            return data.get("id", 0)
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url)
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to post BB comment: {e}")


def has_bb_complexity_comment(
    workspace: str,
    repo: str,
    pr_id: int,
    email: str,
    token: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[int]:
    """Check if a BB PR already has a complexity comment.

    Returns:
        The complexity score if found, None otherwise.
    """
    url = (
        f"{BITBUCKET_API_BASE_URL}/repositories/{workspace}/{repo}"
        f"/pullrequests/{pr_id}/comments"
    )
    auth = _build_auth(email, token)
    page = 1

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            while True:
                response = client.get(
                    url, auth=auth, params={"pagelen": BITBUCKET_PER_PAGE, "page": page}
                )
                response.raise_for_status()
                data = response.json()

                for comment in data.get("values", []):
                    raw = (comment.get("content") or {}).get("raw", "")
                    if COMPLEXITY_MARKER in raw:
                        m = re.search(r"\*\*Score:\*\*\s*(\d+)/10", raw)
                        if m:
                            return int(m.group(1))
                        return 0

                if not data.get("next"):
                    break
                page += 1

        return None
    except httpx.HTTPStatusError as e:
        raise BitbucketAPIError(e.response.status_code, e.response.text[:500], url)
    except httpx.RequestError as e:
        raise RuntimeError(f"Failed to check BB complexity comment: {e}")
