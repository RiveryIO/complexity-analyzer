#!/bin/bash
# Fetch June 2024 → start of complexity-report.csv PR URLs to cache (no analysis or labeling).
# CSV begins at 2025-05-12; this caches PRs from 2024-06-01 through 2025-05-11.
# Run with --fetch-only first to see the count; later run without it to analyze and label.

cd "$(dirname "$0")/.."

complexity-cli batch-analyze \
  --all-repos \
  --since 2024-06-01 \
  --until 2025-05-11 \
  --overwrite \
  --fetch-only \
  --cache cache/jun-2024-to-csv-start-prs.txt

echo "PR URLs cached to: cache/jun-2024-to-csv-start-prs.txt"
