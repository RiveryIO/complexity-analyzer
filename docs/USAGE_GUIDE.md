# Usage Guide

## 1. Setup

1. **Install**:
   ```bash
   pip install -e .
   ```

2. **Configure** (copy `env.example` to `.env`):
   - `GH_TOKEN` or `GITHUB_TOKEN` – required for private repos and labeling
   - `OPENAI_API_KEY` – for `--provider openai`
   - `ANTHROPIC_API_KEY` – for `--provider anthropic`

3. **Verify**:
   ```bash
   complexity-cli verify-settings
   ```

## 2. First Run

### Option A: Start from scratch
```bash
# Fetch and analyze last 14 days
complexity-cli batch-analyze --all-repos --days 14 -o complexity-report.csv --provider anthropic
```

### Option B: Export existing labels (no LLM)
```bash
complexity-cli export-labels --org myorg --since 2024-01-01 --until 2024-12-31 -o complexity-report.csv
```

### Option C: Migrate legacy CSV
If you have an old `complexity-report.csv` with only `pr_url`, `complexity`, `author`:
```bash
complexity-cli migrate-csv
```

## 3. Incremental Sync

After the first run, subsequent batch-analyze or export-labels only fetches **new** PRs (merged after the latest in CSV):

```bash
# Fetches only PRs merged after your latest CSV row
complexity-cli batch-analyze --all-repos --days 7 -o complexity-report.csv
```

To force a full re-fetch:
```bash
complexity-cli batch-analyze --all-repos --days 90 -o complexity-report.csv --overwrite
```

## 4. Generate Reports

```bash
complexity-cli generate-reports -i complexity-report.csv -o reports
```

Output: 17 PNG files in `reports/` (e.g. `01-complexity-volume-over-time.png`).

## 5. Team Mapping (Optional)

Copy `teams.yaml.example` to `teams.yaml` and map repos to teams:

```yaml
owner/repo: "Platform"
other-org/backend: "Backend"
```

Reports that group by team will use these mappings.
