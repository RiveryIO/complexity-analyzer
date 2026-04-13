# Configuration

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GH_TOKEN` / `GITHUB_TOKEN` | For private repos, labeling | GitHub API token |
| `OPENAI_API_KEY` | For `--provider openai` | OpenAI API key |
| `ANTHROPIC_API_KEY` | For `--provider anthropic` | Anthropic API key |
| `GH_TOKENS` / `GITHUB_TOKENS` | Optional | Comma-separated tokens for rotation |
| `BITBUCKET_EMAIL` | For Bitbucket repos | Bitbucket account email |
| `BITBUCKET_API_TOKEN` / `BITBUCKET_APP_PASSWORD` | For Bitbucket repos | Bitbucket API token or app password |

## Team Mapping

**Files**: `github-teams.cfg`, `bitbucket-teams.cfg`, `teams.yaml`, `teams.yml`, or `teams.txt` in project root

Maps developer usernames to teams for per-team reports and company-wide aggregation. Multiple files will be merged (e.g., `github-teams.cfg` for GitHub usernames and `bitbucket-teams.cfg` for Bitbucket usernames).

**Text format** (recommended):

```
# github-teams.cfg (GitHub usernames)
[Platform] alice bob charlie
[Backend] dave eve
[Frontend] frank grace

# bitbucket-teams.cfg (Bitbucket usernames)
[Platform] alice_bb bob_bb charlie_bb
[Backend] dave_bb eve_bb
[Frontend] frank_bb grace_bb
```

**YAML format**:

```yaml
Platform: [alice, bob, charlie]
Backend: [dave, eve]
Frontend: [frank, grace]
```

**Note**: Usernames are platform-specific. GitHub and Bitbucket usernames for the same developer may differ (e.g., `alice` on GitHub vs `alice_bb` on Bitbucket), so maintain separate config files for each platform.

## Verification

Run `complexity-cli verify-settings` to check:
- GH_TOKEN present
- OPENAI_API_KEY / ANTHROPIC_API_KEY (as needed)
- GitHub rate limit
- CSV path exists
- Team config valid
- Required CSV columns present

Remediation hints are shown for failed checks.
