# CSV Schema

## Canonical Columns

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `pr_url` | string | input | PR link (primary key) |
| `complexity` | int | LLM | Score 1–10 |
| `developer` | string | GitHub | Author login |
| `date` | date | merged_at | Primary date for reporting |
| `team` | string | config | From teams.yaml |
| `merged_at` | datetime | GitHub | When PR was merged |
| `created_at` | datetime | GitHub | When PR was opened |
| `lines_added` | int | GitHub | Additions |
| `lines_deleted` | int | GitHub | Deletions |
| `explanation` | string | LLM | Audit trail |

## Legacy Compatibility

- `author` is accepted as alias for `developer`
- `PR link` is accepted as alias for `pr_url`
- Rows missing `merged_at`, `created_at`, `lines_added`, `lines_deleted` can be enriched via `migrate-csv`

## Migration

Run `complexity-cli migrate-csv` to:
1. Fetch missing `merged_at`, `created_at`, `lines_added`, `lines_deleted` from GitHub
2. Fill `team` from teams.yaml
3. Write enriched CSV with full schema
