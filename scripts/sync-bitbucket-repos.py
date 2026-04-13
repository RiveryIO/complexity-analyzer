#!/usr/bin/env python3
"""Sync Bitbucket PRs from multiple repositories."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path to import CLI modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.bitbucket import search_bb_merged_prs
from cli.config import get_bitbucket_credentials
from cli.csv_handler import load_completed_prs_from_csv

# Configuration
REPOS = [
    "boomii/kh-commons",
    "boomii/kh-kubernetes",
    "boomii/kh-retrieve-api",
    "boomii/kh-terraform",
    "boomii/kh-worker",
    "boomii/knowledge-hub-api",
    "boomii/knowledge-hub-frontend",
    "boomii/rivery-api-service",
    "boomii/rivery-dev-agent",
    "boomii/rivery-fire-service",
]

DAYS_BACK = 180
CSV_FILE = "complexity-report.csv"
NEW_PRS_FILE = "new-bitbucket-prs.txt"
PROVIDER = "anthropic"

def main():
    print(f"🔄 Syncing Bitbucket PRs from {len(REPOS)} repositories (last {DAYS_BACK} days)...")
    print()

    # Get Bitbucket credentials
    bb_email, bb_token = get_bitbucket_credentials()
    if not bb_email or not bb_token:
        print("❌ Error: BITBUCKET_EMAIL and BITBUCKET_API_TOKEN are required")
        sys.exit(1)

    # Calculate date range
    until = datetime.now()
    since = until - timedelta(days=DAYS_BACK)

    # Load existing PRs to avoid duplicates
    existing_prs = set()
    if Path(CSV_FILE).exists():
        try:
            existing_prs = load_completed_prs_from_csv(Path(CSV_FILE))
            print(f"📊 Found {len(existing_prs)} existing PRs in CSV\n")
        except Exception as e:
            print(f"⚠️  Warning: Could not load existing PRs: {e}\n")

    # Process each repo
    all_new_prs = []
    total_fetched = 0

    for repo in REPOS:
        workspace, repo_slug = repo.split('/')
        print(f"📦 Processing {repo}...")

        try:
            # Search for merged PRs
            pr_urls = search_bb_merged_prs(
                workspace,
                repo_slug,
                since,
                until,
                bb_email,
                bb_token,
                progress_callback=lambda m: print(f"   {m}"),
            )

            # Filter out already-analyzed PRs
            new_prs = [url for url in pr_urls if url not in existing_prs]
            total_fetched += len(pr_urls)
            all_new_prs.extend(new_prs)

            print(f"   ✓ Found {len(pr_urls)} PRs ({len(new_prs)} new)")

        except Exception as e:
            print(f"   ⚠️  Error: {e}")

        print()

    # Save new PRs to file
    if all_new_prs:
        with open(NEW_PRS_FILE, 'w') as f:
            for url in all_new_prs:
                f.write(url + '\n')
        print(f"💾 Saved {len(all_new_prs)} new PR URLs to {NEW_PRS_FILE}")
        print()

    # Summary
    print("=" * 60)
    print(f"✅ Sync complete!")
    print(f"   Total PRs found: {total_fetched}")
    print(f"   New PRs to analyze: {len(all_new_prs)}")
    print(f"   Already in CSV: {len(existing_prs)}")
    print()

    if all_new_prs:
        print(f"💡 To analyze the new PRs, run:")
        print(f"   complexity-cli batch-analyze -i {NEW_PRS_FILE} -o {CSV_FILE} --provider {PROVIDER}")
    else:
        print("✓ All Bitbucket PRs are already analyzed!")

if __name__ == "__main__":
    main()
