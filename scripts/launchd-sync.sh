#!/bin/bash
# launchd-sync.sh — wrapper for daily PR complexity sync via LaunchAgent
# Standalone script to avoid macOS Full Disk Access issues with inline plist commands

set -euo pipefail

export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export TIKTOKEN_CACHE_DIR="/Users/ohadperry/.cache/tiktoken-persistent"
export SSL_CERT_FILE="/Users/ohadperry/.ssl/combined_certs.pem"
export REQUESTS_CA_BUNDLE="/Users/ohadperry/.ssl/combined_certs.pem"

REPO_DIR="/Users/ohadperry/Documents/Dev/complexity-analyzer"
LOG_FILE="$REPO_DIR/logs/launchd-sync.log"

cd "$REPO_DIR"

echo "$(date): Starting sync..." >> "$LOG_FILE"

output=$("$REPO_DIR/scripts/sync-new-prs.sh" --days 14 2>&1) || true
metrics=$(echo "$output" | grep '^METRICS:' | tail -1)
found=$(echo "$metrics" | sed 's/.*found=\([0-9]*\).*/\1/')
labeled=$(echo "$metrics" | sed 's/.*labeled=\([0-9]*\).*/\1/')
skipped=$(echo "$metrics" | sed 's/.*skipped=\([0-9]*\).*/\1/')
total=$(echo "$metrics" | sed 's/.*total=\([0-9]*\).*/\1/')

if [ -z "$found" ]; then found=0; fi
if [ -z "$labeled" ]; then labeled=0; fi
if [ -z "$skipped" ]; then skipped=0; fi

# Auto-commit and push CSV if changed
if ! /usr/bin/git diff --quiet complexity-report.csv 2>/dev/null; then
  /usr/bin/git add complexity-report.csv
  /usr/bin/git commit -m "chore: daily sync — $labeled new PRs labeled (total: $total)"
  /usr/bin/git push origin main
  push_status="pushed"
else
  push_status="no changes"
fi

echo "$(date): Done — found=$found labeled=$labeled total=$total git=$push_status" >> "$LOG_FILE"

/opt/homebrew/bin/terminal-notifier \
  -title "PR Complexity Sync" \
  -subtitle "Found $found PRs, labeled $labeled new, skipped $skipped (already in CSV)" \
  -message "Total in DB: $total PRs | Git: $push_status" \
  -group "complexity-sync" \
  -sound default
