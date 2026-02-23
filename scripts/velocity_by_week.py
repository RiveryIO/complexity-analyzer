#!/usr/bin/env python3
"""
Graph R&D velocity by week from complexity-report.csv.

Fetches merge dates from GitHub API and plots PR count + complexity-weighted
velocity per week. Requires: matplotlib, GH_TOKEN or gh auth.
"""

import csv
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv()

from cli.config import get_github_token
from cli.utils import build_github_headers, parse_pr_url

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    print("Error: matplotlib required. Install with: pip install matplotlib")
    sys.exit(1)


def fetch_merged_at(owner: str, repo: str, pr: int, token: str) -> str | None:
    """Fetch merged_at date for a PR from GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}"
    headers = build_github_headers(token)
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data.get("merged_at")
    except Exception:
        return None


def load_csv(csv_path: Path) -> list[dict]:
    """Load complexity report CSV."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_url = row.get("pr_url", "").strip()
            if not pr_url:
                continue
            try:
                complexity = int(row.get("complexity", 0) or 0)
            except ValueError:
                complexity = 0
            rows.append({"pr_url": pr_url, "complexity": complexity})
    return rows


def main():
    csv_path = Path(__file__).parent.parent / "complexity-report.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    token = get_github_token()
    if not token:
        print("Error: GH_TOKEN or GITHUB_TOKEN required. Run: gh auth login")
        sys.exit(1)

    rows = load_csv(csv_path)
    print(f"Loaded {len(rows)} PRs from {csv_path}")

    # Fetch merge dates
    week_pr_count = defaultdict(int)
    week_complexity_sum = defaultdict(int)

    for i, row in enumerate(rows):
        try:
            owner, repo, pr = parse_pr_url(row["pr_url"])
        except ValueError:
            continue

        merged_at = fetch_merged_at(owner, repo, pr, token)
        time.sleep(0.2)  # Avoid rate limits
        if not merged_at:
            continue

        dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        week_start = dt.date() - timedelta(days=dt.weekday())  # Monday
        week_key = week_start.isoformat()

        week_pr_count[week_key] += 1
        week_complexity_sum[week_key] += row["complexity"]

        if (i + 1) % 25 == 0:
            print(f"  Fetched {i + 1}/{len(rows)} merge dates...")

    if not week_pr_count:
        print("Error: No merge dates found. Check token permissions.")
        sys.exit(1)

    # Sort weeks
    weeks = sorted(week_pr_count.keys())
    pr_counts = [week_pr_count[w] for w in weeks]
    complexity_sums = [week_complexity_sum[w] for w in weeks]

    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    x = range(len(weeks))
    labels = []
    for w in weeks:
        mon = datetime.strptime(w, "%Y-%m-%d").date()
        sun = mon + timedelta(days=6)
        labels.append(f"{mon.strftime('%b %d')}–{sun.strftime('%d')}")

    ax1.bar(x, pr_counts, color="#2563eb", alpha=0.85, edgecolor="#1e40af")
    ax1.set_ylabel("PRs merged", fontsize=11)
    ax1.set_title("R&D Velocity by Week", fontsize=14, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.grid(axis="y", alpha=0.3)

    ax2.bar(x, complexity_sums, color="#059669", alpha=0.85, edgecolor="#047857")
    ax2.set_ylabel("Complexity points", fontsize=11)
    ax2.set_title("Complexity-weighted velocity (sum of scores)", fontsize=12)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha="right")
    ax2.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    out_path = csv_path.parent / "velocity-by-week.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
