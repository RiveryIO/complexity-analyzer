---
name: verify-settings
description: Verifies that you have all settings required to pull data and generate reports. Use when the user asks to verify setup, check config, "do I have everything?", or before running batch-analyze or generate-reports.
---

# Verify Settings

Verifies all settings required to pull data and generate reports. Helps identify missing configuration and suggests remediation.

## When to Use

- User asks: "Do I have everything?", "Verify my setup", "Check config"
- Before running batch-analyze or generate-reports
- Troubleshooting "missing token" or "404" errors

## Run

```bash
complexity-cli verify-settings
```

## Checks Performed

| Check | Remediation |
|-------|-------------|
| GH_TOKEN / GITHUB_TOKEN | Set `GH_TOKEN` or run `gh auth login` |
| OPENAI_API_KEY | Set for `--provider openai` |
| ANTHROPIC_API_KEY | Set for `--provider anthropic` |
| GitHub rate limit | Wait for reset or add tokens |
| CSV path | Ensure `complexity-report.csv` exists (or run batch-analyze) |
| Team config | Copy `teams.yaml.example` to `teams.yaml` (optional) |
| CSV columns | Run `complexity-cli migrate-csv` to enrich legacy rows |

## Options

| Option | Description |
|--------|-------------|
| `--csv PATH` | Custom CSV path (default: complexity-report.csv) |
| `--csv-required` | Fail when CSV is missing |

## Output

- ✓ / ✗ for each check
- Hints for failed checks
- Exit code 1 if any check fails
