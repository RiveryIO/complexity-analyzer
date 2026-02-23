# Configuration

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GH_TOKEN` / `GITHUB_TOKEN` | For private repos, labeling | GitHub API token |
| `OPENAI_API_KEY` | For `--provider openai` | OpenAI API key |
| `ANTHROPIC_API_KEY` | For `--provider anthropic` | Anthropic API key |
| `GH_TOKENS` / `GITHUB_TOKENS` | Optional | Comma-separated tokens for rotation |

## Team Mapping

**File**: `teams.yaml` or `teams.json` in project root

```yaml
owner/repo: "Team Name"
other-org/other-repo: "Platform"
```

## Verification

Run `complexity-cli verify-settings` to check:
- GH_TOKEN present
- OPENAI_API_KEY / ANTHROPIC_API_KEY (as needed)
- GitHub rate limit
- CSV path exists
- Team config valid
- Required CSV columns present

Remediation hints are shown for failed checks.
