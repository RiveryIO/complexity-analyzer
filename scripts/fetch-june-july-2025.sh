#!/bin/bash
# Fetch June–July 2025 PRs, add complexity labels if not present.
# Results are saved to complexity-report.csv in the project root.

cd "$(dirname "$0")/.."
OUTPUT_CSV="$(pwd)/complexity-report.csv"

complexity-cli batch-analyze \
  --all-repos \
  --since 2025-06-01 \
  --until 2025-07-31 \
  -o "$OUTPUT_CSV" \
  --overwrite \
  --label \
  --provider anthropic \
  --cache cache/june-july-2025-prs.txt

echo "Results saved to: $OUTPUT_CSV"
