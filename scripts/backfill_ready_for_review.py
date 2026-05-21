"""One-off backfill: populate `ready_for_review_at` for existing PRs in complexity-report.csv.

Re-fetches only the draft timestamp from GitHub events / Bitbucket activity. Skips
rows that already have a value. Use --limit to bound API cost while validating.
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.github import fetch_ready_for_review_at  # noqa: E402
from cli.bitbucket import fetch_bb_ready_for_review_at  # noqa: E402


GH_RE = "github.com/"
BB_RE = "bitbucket.org/"


def parse_url(url: str):
    if GH_RE in url:
        # https://github.com/owner/repo/pull/N
        parts = url.rstrip("/").split("/")
        return ("github", parts[-4], parts[-3], int(parts[-1]))
    if BB_RE in url:
        # https://bitbucket.org/ws/repo/pull-requests/N
        parts = url.rstrip("/").split("/")
        return ("bitbucket", parts[-4], parts[-3], int(parts[-1]))
    return (None, None, None, None)


def fetch_one(url: str, gh_token: str, bb_email: str, bb_token: str):
    kind, ns, repo, pr = parse_url(url)
    try:
        if kind == "github":
            return url, fetch_ready_for_review_at(ns, repo, pr, token=gh_token), None
        if kind == "bitbucket":
            return url, fetch_bb_ready_for_review_at(ns, repo, pr, bb_email, bb_token), None
        return url, None, "unknown_url"
    except Exception as e:
        return url, None, type(e).__name__ + ": " + str(e)[:120]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="complexity-report.csv")
    ap.add_argument("--limit", type=int, default=0, help="Max PRs to fetch (0 = all)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--newest-first", action="store_true", default=True)
    ap.add_argument(
        "--only-new", action="store_true",
        help="Skip rows that already have ready_for_review_at populated",
    )
    args = ap.parse_args()

    gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    bb_email = os.environ.get("BITBUCKET_EMAIL") or ""
    bb_token = os.environ.get("BITBUCKET_API_TOKEN") or os.environ.get("BITBUCKET_APP_PASSWORD") or ""

    df = pd.read_csv(args.csv)
    if "ready_for_review_at" not in df.columns:
        # Insert column right after created_at to match canonical schema
        cols = list(df.columns)
        if "created_at" in cols:
            cols.insert(cols.index("created_at") + 1, "ready_for_review_at")
        else:
            cols.append("ready_for_review_at")
        df["ready_for_review_at"] = ""
        df = df[cols]

    # Pick target rows
    if args.newest_first:
        df_sorted = df.sort_values("merged_at", ascending=False, na_position="last")
    else:
        df_sorted = df

    candidates = df_sorted
    if args.only_new:
        candidates = candidates[candidates["ready_for_review_at"].fillna("").astype(str).str.strip() == ""]
    if args.limit:
        candidates = candidates.head(args.limit)

    urls = candidates["pr_url"].dropna().tolist()
    print(f"Fetching ready_for_review_at for {len(urls)} PRs (workers={args.workers})")

    results = {}
    errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(fetch_one, u, gh_token, bb_email, bb_token): u for u in urls}
        done = 0
        for fut in as_completed(futures):
            url, ts, err = fut.result()
            done += 1
            if err:
                errors += 1
                if errors <= 5:
                    print(f"  ! {url}: {err}", file=sys.stderr)
            results[url] = ts
            if done % 50 == 0 or done == len(urls):
                hits = sum(1 for v in results.values() if v)
                print(f"  progress: {done}/{len(urls)}  (with draft ts: {hits})")

    # Update df
    df["ready_for_review_at"] = df.apply(
        lambda r: results.get(r["pr_url"], r.get("ready_for_review_at") or "") or r.get("ready_for_review_at") or "",
        axis=1,
    )

    df.to_csv(args.csv, index=False)
    hits = sum(1 for v in results.values() if v)
    print(f"\nDone. {hits} PRs had a draft→ready transition, {errors} errors. CSV updated: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
