# Feature Overview

## Commands

| Command | Description |
|---------|-------------|
| `analyze-pr` | Analyze a single PR and output complexity score |
| `batch-analyze` | Analyze multiple PRs (file, org, or all-repos) with optional labeling |
| `export-labels` | Export existing complexity labels from GitHub to CSV (no LLM) |
| `label-pr` | Analyze a PR and apply a complexity label |
| `migrate-csv` | Enrich existing CSV rows with merged_at, created_at, lines_added, lines_deleted |
| `generate-reports` | Generate 17 engineering intelligence reports from CSV |
| `verify-settings` | Check that all required settings are configured |
| `rate-limit` | Check GitHub API rate limit status |

## Workflows

### Single PR Analysis
```bash
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123"
```

### Batch Analysis (with incremental fetch)
```bash
# Only fetches PRs merged after latest in CSV (performance)
complexity-cli batch-analyze --all-repos --days 30 -o complexity-report.csv

# Full re-sync (ignore existing CSV)
complexity-cli batch-analyze --all-repos --days 30 -o complexity-report.csv --overwrite
```

### Export Labels (no LLM)
```bash
complexity-cli export-labels --org myorg --since 2024-01-01 --until 2024-12-31 -o complexity-report.csv
```

### Migrate Legacy CSV
```bash
complexity-cli migrate-csv --input complexity-report.csv --output complexity-report.csv

# Background mode for large files
complexity-cli migrate-csv --background
```

### Generate Reports
```bash
complexity-cli generate-reports -i complexity-report.csv -o reports
```

### Verify Setup
```bash
complexity-cli verify-settings
```

## Key Features

- **Incremental fetch**: By default, only fetches PRs merged after the latest `merged_at` in CSV
- **Team mapping**: `teams.yaml` maps `owner/repo` to team names for reports
- **Parallel reports**: All 17 reports generated in parallel (<10 seconds)
- **Resume**: Batch analysis skips PRs already in CSV
