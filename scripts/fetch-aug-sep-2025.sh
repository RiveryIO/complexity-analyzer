#!/bin/bash
# Fetch August–September 2025 PRs, add complexity labels if not present.
# Run this after June–July 2025 fetch completes.
# Results are saved to complexity-report.csv in the project root.

cd "$(dirname "$0")/.."
OUTPUT_CSV="$(pwd)/complexity-report.csv"

complexity-cli batch-analyze \
  --all-repos \
  --since 2025-08-01 \
  --until 2025-09-30 \
  -o "$OUTPUT_CSV" \
  --overwrite \
  --label \
  --provider anthropic \
  --cache cache/aug-sep-2025-prs.txt

echo "Results saved to: $OUTPUT_CSV"
