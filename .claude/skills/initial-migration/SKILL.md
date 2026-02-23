---
name: initial-migration
description: Guides initial migration, backfill, or first-time sync of historical PR data. Use when the user asks to migrate, backfill, do initial sync, or set up historical data.
---

# Initial Migration

Guides the user through migrating existing data, backfilling historical PRs, or doing a first-time sync.

## When to Use

- User asks: "migrate my data", "backfill", "initial sync", "set up historical data"
- First-time setup of the engineering intelligence dashboard
- Enriching legacy CSV with new columns

## Workflow

1. **Verify settings** (run verify-settings skill first):
   ```bash
   complexity-cli verify-settings
   ```

2. **Migrate existing CSV** (if complexity-report.csv exists with legacy columns):
   ```bash
   complexity-cli migrate-csv --input complexity-report.csv --output complexity-report.csv
   ```
   For long migrations, use background mode:
   ```bash
   complexity-cli migrate-csv --background
   ```

3. **Batch analyze** for full history (or incremental from latest CSV):
   ```bash
   # Last 30 days, all repos
   complexity-cli batch-analyze --all-repos --days 30 -o complexity-report.csv --provider anthropic

   # Custom date range
   complexity-cli batch-analyze --all-repos --since 2024-01-01 --until 2024-12-31 -o complexity-report.csv
   ```

4. **Generate reports** (after data is ready):
   ```bash
   complexity-cli generate-reports
   ```

## Options

| Step | Option | Description |
|------|--------|-------------|
| migrate-csv | `--background` | Run in background, log to reports/migration.log |
| batch-analyze | `--overwrite` | Full sync (ignore incremental fetch) |
| batch-analyze | `--workers N` | Parallel workers for faster analysis |

## Notes

- Incremental fetch is default: only new PRs (after latest merged_at in CSV) are fetched
- Use `--overwrite` for full re-sync when needed
- Team mapping requires `teams.yaml` (copy from teams.yaml.example)
