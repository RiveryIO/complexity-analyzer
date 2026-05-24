#!/bin/bash
# launchd-sync.sh — wrapper for daily PR complexity sync via LaunchAgent
# Standalone script to avoid macOS Full Disk Access issues with inline plist commands

# Do not enable `set -e` / `pipefail` globally — grep-based metric parsing
# below legitimately returns non-zero when there's nothing to extract, and we
# must still reach the commit/push stage.
set -u

export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export TIKTOKEN_CACHE_DIR="/Users/ohadperry/.cache/tiktoken-persistent"
export SSL_CERT_FILE="/Users/ohadperry/.ssl/combined_certs.pem"
export REQUESTS_CA_BUNDLE="/Users/ohadperry/.ssl/combined_certs.pem"

REPO_DIR="/Users/ohadperry/Documents/Dev/complexity-analyzer"
LOG_FILE="$REPO_DIR/logs/launchd-sync.log"
TOKEN_FILE="$HOME/.config/gh-token"

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
if [ -z "$total" ]; then total=0; fi

# Sync Jira features
echo "$(date): Syncing Jira features..." >> "$LOG_FILE"
jira_output=$(python3 "$REPO_DIR/scripts/sync-jira-features.py" --days 14 2>&1) || true
jira_new=$(echo "$jira_output" | grep -o '[0-9]* new' | grep -o '[0-9]*' | tail -1 || true)
jira_updated=$(echo "$jira_output" | grep -o '[0-9]* updated' | grep -o '[0-9]*' | tail -1 || true)
if [ -z "$jira_new" ]; then jira_new=0; fi
if [ -z "$jira_updated" ]; then jira_updated=0; fi
echo "$(date): Jira sync — new=$jira_new updated=$jira_updated" >> "$LOG_FILE"

# Auto-commit and push CSVs if changed
changed_files=""
if ! /usr/bin/git diff --quiet complexity-report.csv 2>/dev/null; then
  changed_files="$changed_files complexity-report.csv"
fi
if ! /usr/bin/git diff --quiet features-released.csv 2>/dev/null; then
  changed_files="$changed_files features-released.csv"
fi

push_status="no changes"
if [ -n "$changed_files" ]; then
  /usr/bin/git add $changed_files
  /usr/bin/git commit -m "chore: daily sync — $labeled new PRs labeled, $jira_new jira features added (total PRs: $total)" >> "$LOG_FILE" 2>&1

  # Push using token from file — osxkeychain credential helper is unreliable
  # from launchd. Fall back to origin remote if token file missing.
  if [ -r "$TOKEN_FILE" ]; then
    GH_TOKEN_VALUE=$(tr -d '\n\r' < "$TOKEN_FILE")
    PUSH_URL="https://x-access-token:${GH_TOKEN_VALUE}@github.com/RiveryIO/complexity-analyzer.git"
    if /usr/bin/git push "$PUSH_URL" main >> "$LOG_FILE" 2>&1; then
      push_status="pushed"
    else
      push_status="push-failed"
    fi
  else
    if /usr/bin/git push origin main >> "$LOG_FILE" 2>&1; then
      push_status="pushed"
    else
      push_status="push-failed-no-token"
    fi
  fi
fi

echo "$(date): Done — found=$found labeled=$labeled total=$total jira_new=$jira_new git=$push_status" >> "$LOG_FILE"

/opt/homebrew/bin/terminal-notifier \
  -title "PR Complexity Sync" \
  -subtitle "Found $found PRs, labeled $labeled new, skipped $skipped (already in CSV)" \
  -message "Total in DB: $total PRs | Git: $push_status" \
  -group "complexity-sync" \
  -sound default
