#!/bin/bash
#
# Incremental PR complexity sync
# ─────────────────────────────────
# Finds PRs merged since the latest entry in complexity-report.csv,
# scores them with an LLM, labels them on GitHub (complexity:N),
# and appends them to the CSV.
#
# Designed to run on a recurring schedule (e.g. daily cron / launchd).
#
# Usage:
#   ./scripts/sync-new-prs.sh              # default: 14-day search window, 3 workers
#   ./scripts/sync-new-prs.sh --days 7     # override search window
#   ./scripts/sync-new-prs.sh --workers 5  # override parallelism
#   DRY_RUN=1 ./scripts/sync-new-prs.sh   # fetch-only, no analysis or labeling

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

CSV_FILE="complexity-report.csv"
REPOS_FILE="repos.txt"
LOG_FILE="logs/sync-$(date +%Y%m%d-%H%M%S).log"

DAYS=14
WORKERS=3

while [[ $# -gt 0 ]]; do
    case $1 in
        --days)   DAYS="$2";    shift 2 ;;
        --workers) WORKERS="$2"; shift 2 ;;
        *)        echo "Unknown option: $1"; exit 1 ;;
    esac
done

BACKUP_DIR="backups"
BACKUP_RETENTION_DAYS=7

mkdir -p logs "$BACKUP_DIR"

# Backup CSV before any changes
if [[ -f "$CSV_FILE" ]]; then
    BACKUP_FILE="$BACKUP_DIR/complexity-report-$(date +%Y%m%d-%H%M%S).csv"
    cp "$CSV_FILE" "$BACKUP_FILE"
    echo "Backup: $BACKUP_FILE"
fi

# Prune backups older than retention period
find "$BACKUP_DIR" -name "complexity-report-*.csv" -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true

echo "=== PR Complexity Sync ===" | tee -a "$LOG_FILE"
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "Search window: last $DAYS days" | tee -a "$LOG_FILE"
echo "Workers: $WORKERS" | tee -a "$LOG_FILE"

if [[ ! -f "$CSV_FILE" ]]; then
    echo "Warning: $CSV_FILE not found — will create a fresh one" | tee -a "$LOG_FILE"
fi

if [[ ! -f "$REPOS_FILE" ]]; then
    echo "Error: $REPOS_FILE not found. Create it with one owner/repo per line." | tee -a "$LOG_FILE"
    exit 1
fi

LATEST_MERGED=$(tail -1 "$CSV_FILE" 2>/dev/null | awk -F',' '{print $6}' || echo "none")
echo "Latest merged_at in CSV: $LATEST_MERGED" | tee -a "$LOG_FILE"

ROWS_BEFORE=0
if [[ -f "$CSV_FILE" ]]; then
    ROWS_BEFORE=$(( $(wc -l < "$CSV_FILE" | tr -d ' ') - 1 ))
fi
echo "Rows before: $ROWS_BEFORE" | tee -a "$LOG_FILE"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "DRY_RUN=1 — fetching PR list only, no analysis or labeling" | tee -a "$LOG_FILE"
    complexity-cli batch-analyze \
        --repos-file "$REPOS_FILE" \
        --days "$DAYS" \
        --output "$CSV_FILE" \
        --fetch-only \
        --cache "cache/sync-dryrun-$(date +%Y%m%d).txt" \
        2>&1 | tee -a "$LOG_FILE"
    echo "Done (dry run). Check the cache file for the PR list." | tee -a "$LOG_FILE"
    exit 0
fi

CLI_OUTPUT=$(complexity-cli batch-analyze \
    --repos-file "$REPOS_FILE" \
    --days "$DAYS" \
    --output "$CSV_FILE" \
    --label \
    --workers "$WORKERS" \
    --resume \
    2>&1)

echo "$CLI_OUTPUT" | tee -a "$LOG_FILE"

FOUND=$(echo "$CLI_OUTPUT" | grep -oE 'Found [0-9]+ PRs' | head -1 | grep -oE '[0-9]+' || echo "0")

ROWS_AFTER=0
if [[ -f "$CSV_FILE" ]]; then
    ROWS_AFTER=$(( $(wc -l < "$CSV_FILE" | tr -d ' ') - 1 ))
fi
UPDATED=$(( ROWS_AFTER - ROWS_BEFORE ))

NEW_LATEST=$(tail -1 "$CSV_FILE" 2>/dev/null | awk -F',' '{print $6}' || echo "none")

echo "──────────────────────────" | tee -a "$LOG_FILE"
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
echo "New latest merged_at: $NEW_LATEST" | tee -a "$LOG_FILE"
echo "Total CSV rows: $ROWS_AFTER" | tee -a "$LOG_FILE"
echo "METRICS: found=$FOUND labeled=$UPDATED total=$ROWS_AFTER" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE"
