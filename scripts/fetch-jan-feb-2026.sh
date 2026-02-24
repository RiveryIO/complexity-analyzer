#!/bin/bash
# Fetch January–February 2026 PR URLs to cache (no analysis or labeling).
# Run with --fetch-only first, then later run without it to analyze and label.

cd "$(dirname "$0")/.."

complexity-cli batch-analyze \
  --all-repos \
  --since 2026-01-01 \
  --until 2026-02-28 \
  --overwrite \
  --fetch-only \
  --cache cache/jan-feb-2026-prs.txt

echo "PR URLs cached to: cache/jan-feb-2026-prs.txt"
