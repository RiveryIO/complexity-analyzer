---
name: label-unlabeled-prs
description: Labels all unlabeled merged PRs from the last X days with complexity scores. Use when the user asks to label PRs, add complexity labels to merged PRs, or backfill labels for unlabeled PRs. Defaults to last 7 days.
---

# Label Unlabeled Merged PRs

Labels merged PRs that lack a complexity label. Skips PRs that already have a `complexity:N` label.

## Prerequisites

- `GH_TOKEN` or `gh auth token` (required)
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (for LLM analysis)

## Run

```bash
# Default: last 7 days, all repos, merged PRs only
complexity-cli batch-analyze --all-repos --days 7 --label --provider anthropic

# Custom days (e.g. last 14 days)
complexity-cli batch-analyze --all-repos --days 14 --label --provider anthropic

# With OpenAI instead
complexity-cli batch-analyze --all-repos --days 7 --label --provider openai
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | 7 | Number of days to look back |
| `--provider` | openai | anthropic, openai, or bedrock |
| `--label-prefix` | complexity: | Label format (e.g. complexity:5) |
| `--force` | false | Re-analyze and overwrite existing labels |
| `--workers` | 1 | Parallel workers (increase for faster runs) |

## Output

- Labels applied to PRs (e.g. `complexity:5`)
- Explanation posted as PR comment
- CSV written to `complexity-report.csv` in project root
