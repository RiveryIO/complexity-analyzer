#!/usr/bin/env python3
"""
One-shot backfill: sets approved_by for GitHub PRs merged in the last 30 days.

Usage:
    python scripts/backfill-approvals.py

Requires:
    GH_TOKEN or GITHUB_TOKEN env var with repo read access.

Run ONCE after deploying the approved_by column. Safe to re-run — skips rows
that already have approved_by set.
"""

import csv
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = PROJECT_DIR / "complexity-report.csv"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=30)
SLEEP_BETWEEN_REQUESTS = 0.3  # seconds — stays well within GitHub rate limits


def _get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: set GH_TOKEN or GITHUB_TOKEN", file=sys.stderr)
        sys.exit(1)
    return token


def _parse_github_url(url: str):
    """Parse 'https://github.com/owner/repo/pull/123'
    → (owner, repo, pr_number)."""
    parts = url.rstrip("/").split("/")
    return parts[-4], parts[-3], int(parts[-1])


def _fetch_first_approver(owner: str, repo: str, pr: int, token: str) -> str:
    """Return login of first APPROVED reviewer, or '' if none."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        reviews = resp.json()
        approved = [r for r in reviews if r.get("state") == "APPROVED"]
        approved.sort(key=lambda r: r.get("submitted_at", ""))
        return approved[0]["user"]["login"] if approved else ""
    except Exception as e:
        print(f"  Warning: {e}", file=sys.stderr)
        return ""


def main() -> None:
    if not CSV_FILE.exists():
        print(f"Error: {CSV_FILE} not found", file=sys.stderr)
        sys.exit(1)

    token = _get_token()

    with CSV_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "approved_by" not in fieldnames:
        print(
            "Error: 'approved_by' column not found. "
            "Deploy the schema change (Task 1) first.",
            file=sys.stderr,
        )
        sys.exit(1)

    to_backfill = []
    for row in rows:
        if row.get("approved_by", "").strip():
            continue  # Already populated — skip
        if "github.com" not in row.get("pr_url", ""):
            continue  # Bitbucket PRs have no GitHub reviews API
        merged_at = row.get("merged_at", "")
        if not merged_at:
            continue
        try:
            merged_dt = datetime.fromisoformat(
                merged_at.replace("Z", "+00:00")
            )
        except ValueError:
            continue
        if merged_dt >= CUTOFF:
            to_backfill.append(row)

    print(
        f"Found {len(to_backfill)} GitHub PRs in last 30 days"
        " without approved_by"
    )
    if not to_backfill:
        print("Nothing to do.")
        return

    filled = 0
    for i, row in enumerate(to_backfill, 1):
        pr_url = row["pr_url"]
        try:
            owner, repo, pr_num = _parse_github_url(pr_url)
        except (IndexError, ValueError):
            print(
                f"  [{i}/{len(to_backfill)}] Skipping malformed URL: {pr_url}"
            )
            continue

        print(f"  [{i}/{len(to_backfill)}] {pr_url} ...", end=" ", flush=True)
        approver = _fetch_first_approver(owner, repo, pr_num, token)
        row["approved_by"] = approver
        filled += 1
        print(approver or "(none)")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    with CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Updated {filled} rows.")


if __name__ == "__main__":
    main()
