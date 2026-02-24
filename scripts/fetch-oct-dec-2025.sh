#!/bin/bash
# Fetch October–December 2025 PR URLs to cache (no analysis or labeling).
# Run with --fetch-only first, then later run without it to analyze and label.

cd "$(dirname "$0")/.."

complexity-cli batch-analyze \
  --all-repos \
  --since 2025-10-01 \
  --until 2025-12-31 \
  --overwrite \
  --fetch-only \
  --cache cache/oct-dec-2025-prs.txt

echo "PR URLs cached to: cache/oct-dec-2025-prs.txt"
