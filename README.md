# Complexity CLI

A command-line tool that uses LLMs to analyze the complexity of GitHub pull requests. It helps engineering teams measure velocity in a way that actually reflects the work being done—not just lines of code changed.

## Documentation

- **[How Complexity Analysis Works](docs/COMPLEXITY_ANALYSIS.md)** — End-to-end flow, scoring factors, and fine-tuning for your organization

## Why Measure Complexity?

Traditional engineering metrics like lines of code, number of commits, or PR count don't capture what really matters: **how hard was the work?**

A 500-line PR that renames a variable across a codebase is not the same as a 50-line PR that fixes a subtle race condition. Yet simple metrics treat them the same—or worse, reward the trivial change for being "bigger."

Complexity scoring flips this around. By analyzing what a PR actually does—the logic changes, the number of systems touched, the cognitive load required to review it—we get a score that better represents the engineering effort involved.

This enables:

- **Fairer velocity tracking** — Teams get credit for hard problems, not just high PR counts
- **Better sprint planning** — Historical complexity data helps estimate future work
- **Improved code review** — Reviewers can prioritize their time on genuinely complex changes
- **Meaningful retrospectives** — Discuss what made certain PRs complex, not just how many shipped

## How It Works

1. **Fetch PR**: Downloads the PR diff and metadata from GitHub API
2. **Process Diff**:
   - Redacts secrets and emails
   - Filters out binary files, lockfiles, and vendor directories
   - Truncates to token limit while preserving structure
   - Builds statistics (additions, deletions, file counts, languages)
3. **Analyze**: Sends formatted prompt to LLM with diff excerpt, stats, and title
4. **Score**: Parses LLM response and returns complexity score (1-10) with explanation

## Complexity Scoring Framework

PRs are scored on a scale of 1 to 10. When computing team velocity, we recommend weighting scores using t-shirt sizes:

| Score | Size | Weight | Description |
|-------|------|--------|-------------|
| 1-2 | XS | 0 | Trivial changes (typos, config tweaks, simple fixes) |
| 3 | S | 1 | Small, straightforward changes |
| 4 | M | 2 | Medium complexity, moderate effort |
| 5-6 | L | 3 | Large changes, multiple components affected |
| 7+ | XL | 4 | Complex architectural changes, high risk |

**Example velocity calculation:**

If a team completed 5 PRs with scores [2, 3, 4, 6, 8], the weighted velocity would be:
- Score 2 (XS): 0
- Score 3 (S): 1
- Score 4 (M): 2
- Score 6 (L): 3
- Score 8 (XL): 4

**Total velocity: 10 points**

This weighting system normalizes velocity by giving appropriate credit for complex work while filtering out trivial changes that don't reflect meaningful engineering effort.

## Installation

Install from source:

```bash
git clone <repo-url>
cd complexity-cli
pip install -e .
```

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `analyze-pr` | Analyze a single PR and output complexity score |
| `label-pr` | Analyze a PR and apply a complexity label to it |
| `batch-analyze` | Analyze multiple PRs (with optional labeling) |
| `rate-limit` | Check GitHub API rate limit status |

### Basic Usage

```bash
export OPENAI_API_KEY="your-key"
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123"
```

### Options

- `--prompt-file`, `-p`: Path to custom prompt file (default: embedded prompt)
- `--model`, `-m`: OpenAI model name (default: `gpt-5.2`)
- `--format`, `-f`: Output format: `json` or `markdown` (default: `json`)
- `--out`, `-o`: Write output to file
- `--timeout`, `-t`: Request timeout in seconds (default: 120)
- `--max-tokens`: Maximum tokens for diff excerpt (default: 50000)
- `--hunks-per-file`: Maximum hunks per file (default: 2)
- `--sleep-seconds`: Sleep between GitHub API calls (default: 0.7)
- `--dry-run`: Fetch PR but don't call LLM
- `--provider`: LLM provider: `openai` (default), `anthropic`, or `bedrock`
- `--anthropic-model`: Anthropic model (e.g. `claude-sonnet-4-5-20250929`)
- `--bedrock-model`: Bedrock model ID (e.g. `anthropic.claude-sonnet-4-5-20250929-v1:0`)
- `--bedrock-region`: AWS region for Bedrock (default: `AWS_REGION` or `us-east-1`)

### Environment Variables

- `OPENAI_API_KEY` (required for `--provider openai`): OpenAI API key
- `ANTHROPIC_API_KEY` (required for `--provider anthropic`): Anthropic API key
- `GH_TOKEN` or `GITHUB_TOKEN` (optional): GitHub API token for private repos or higher rate limits

### Anthropic Provider

Use Claude directly via Anthropic's API:

```bash
# Set in .env: ANTHROPIC_API_KEY or ANTROPIC_API_KEY (typo also works)
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123" --provider anthropic
```

### AWS Bedrock Provider

Use Claude on AWS Bedrock instead of OpenAI:

```bash
# Set AWS credentials (profile + region)
export AWS_PROFILE=your-bedrock-profile
export AWS_REGION=us-east-1

# Or use BEDROCK_MODEL_ID to override default (Claude Sonnet 4.5)
export BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0

# Analyze with Bedrock
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123" --provider bedrock
```

Options: `--provider bedrock`, `--bedrock-model`, `--bedrock-region`

### Examples

```bash
# Analyze a PR with default settings
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123"

# Use a different model
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123" --model gpt-4

# Output as markdown
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123" --format markdown

# Save output to file
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123" --out result.json

# Dry run (fetch PR but skip LLM)
complexity-cli analyze-pr "https://github.com/owner/repo/pull/123" --dry-run
```

### Label a Single PR

Analyze a PR and apply a complexity label directly to it on GitHub.

```bash
# Analyze and label a PR with default prefix "complexity:"
complexity-cli label-pr "https://github.com/owner/repo/pull/123"

# Use a custom label prefix
complexity-cli label-pr "https://github.com/owner/repo/pull/123" --label-prefix "cx:"

# Dry run - analyze but don't apply label
complexity-cli label-pr "https://github.com/owner/repo/pull/123" --dry-run
```

This will:
1. Analyze the PR complexity
2. Remove any existing complexity labels (matching the prefix)
3. Add a new label like `complexity:7`

**Note:** A GitHub token with write access is required to update labels.

#### Label PR Options

- `--label-prefix`: Prefix for complexity labels (default: `complexity:`)
- `--dry-run`: Analyze but don't update the label
- All other options from `analyze-pr` are also supported

### Batch Analysis

Analyze multiple PRs in batch mode with resume capability.

#### From Input File

```bash
# Create a file with PR URLs (one per line)
cat > prs.txt << EOF
https://github.com/owner/repo/pull/123
https://github.com/owner/repo/pull/124
https://github.com/owner/repo/pull/125
EOF

# Analyze all PRs (sequential, default)
complexity-cli batch-analyze --input-file prs.txt --output results.csv

# Analyze with 8 parallel workers for faster processing
complexity-cli batch-analyze --input-file prs.txt --output results.csv --workers 8
```

#### From Date Range

```bash
# Analyze all PRs closed in an organization within a date range
complexity-cli batch-analyze \
  --org myorg \
  --since 2024-01-01 \
  --until 2024-01-31 \
  --output results.csv \
  --cache pr-list.txt

# On subsequent runs, the cache file will be used to skip fetching the PR list
complexity-cli batch-analyze \
  --org myorg \
  --since 2024-01-01 \
  --until 2024-01-31 \
  --output results.csv \
  --cache pr-list.txt
```

#### From Repos File

Scan only specific repositories (useful when you don't have org-wide access or want to limit scope):

```bash
# Create a file with repo names (owner/repo per line, # for comments)
cat > repos.txt << EOF
# Repos to scan
myorg/repo-a
myorg/repo-b
EOF

complexity-cli batch-analyze \
  --repos-file repos.txt \
  --since 2024-01-01 \
  --until 2024-01-31 \
  --output results.csv \
  --cache pr-list.txt

# With labeling
complexity-cli batch-analyze --repos-file repos.txt --since 2024-01-01 --until 2024-01-31 --label
```

See `repos.example` for the file format.

#### Batch Labeling

Apply complexity labels to multiple PRs instead of generating CSV output.

```bash
# Label all PRs from a file
complexity-cli batch-analyze --input-file prs.txt --label

# Label PRs closed in a date range
complexity-cli batch-analyze \
  --org myorg \
  --since 2024-01-01 \
  --until 2024-01-31 \
  --label \
  --workers 5

# Force re-labeling PRs that already have complexity labels
complexity-cli batch-analyze --input-file prs.txt --label --force

# Custom label prefix
complexity-cli batch-analyze --input-file prs.txt --label --label-prefix "cx:"
```

When using `--label`:
- PRs that already have a complexity label are skipped (unless `--force` is used)
- Labels are applied in the format `complexity:N` (customizable with `--label-prefix`)
- No `--output` file is required

#### Resume Capability

If the batch analysis is interrupted (Ctrl+C), you can resume by running the same command again. The tool will automatically skip PRs that have already been analyzed by reading the existing output file.

```bash
# First run (interrupted after 10 PRs)
complexity-cli batch-analyze --input-file prs.txt --output results.csv

# Resume (will skip the 10 already-analyzed PRs)
complexity-cli batch-analyze --input-file prs.txt --output results.csv
```

#### Batch Analysis Options

- `--input-file`, `-i`: File containing PR URLs (one per line)
- `--repos-file`, `-r`: File containing repo names (owner/repo per line) for date range search
- `--org`: Organization name (for date range search)
- `--since`: Start date in YYYY-MM-DD format (for date range search)
- `--until`: End date in YYYY-MM-DD format (for date range search)
- `--output`, `-o`: Output CSV file path (required)
- `--cache`: Cache file for PR list (used with date range to avoid re-fetching)
- `--prompt-file`, `-p`: Path to custom prompt file
- `--model`, `-m`: OpenAI model name (default: `gpt-5.2`)
- `--timeout`, `-t`: Request timeout in seconds (default: 120)
- `--max-tokens`: Maximum tokens for diff excerpt (default: 50000)
- `--hunks-per-file`: Maximum hunks per file (default: 2)
- `--sleep-seconds`: Sleep between GitHub API calls (default: 0.7)
- `--resume/--no-resume`: Enable/disable resume from existing output (default: enabled)
- `--workers`, `-w`: Number of parallel workers for concurrent analysis (default: 1, minimum: 1)
- `--label`, `-l`: Label PRs with complexity instead of CSV output
- `--label-prefix`: Prefix for complexity labels (default: `complexity:`, used with `--label`)
- `--force`, `-f`: Re-analyze PRs even if they already have a complexity label

**Note:** When using `--workers` > 1, results are written to the CSV file as soon as each analyzer finishes, so the output order may differ from the input order. This does not affect resume capability - the tool still correctly skips already-analyzed PRs.

## Output Format

### JSON Output (default)

```json
{
  "score": 5,
  "explanation": "Multiple modules/services with non-trivial control flow changes",
  "provider": "openai",
  "model": "gpt-5.1",
  "tokens": 1234,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Markdown Output

```markdown
# PR Complexity Analysis

**Score:** 5/10

**Explanation:** Multiple modules/services with non-trivial control flow changes

**Details:**
- Repository: owner/repo
- PR: #123
- Model: gpt-5.1
- Tokens used: 1234
```

### Batch CSV Output

Batch analysis outputs a CSV file with the following columns:

- `pr_url`: The GitHub PR URL
- `complexity`: The complexity score (1-10)
- `explanation`: The explanation text

Example:

```csv
pr_url,complexity,explanation
https://github.com/owner/repo/pull/123,5,"Multiple modules/services with non-trivial control flow changes"
https://github.com/owner/repo/pull/124,3,"Simple refactoring with minimal changes"
https://github.com/owner/repo/pull/125,8,"Complex architectural changes across multiple services"
```

## Security

- Secrets are never logged or persisted
- API keys are read from environment variables only
- File paths are normalized to prevent directory traversal
- Diffs are redacted to remove secrets and emails

## GitHub Actions Integration

### Automated Daily Labeling

The repository includes a GitHub Actions workflow (`.github/workflows/daily-label.yml`) that automatically labels PRs with their complexity scores.

**Features:**
- Runs daily at 1am UTC
- Labels all PRs closed the previous day
- Can be manually triggered with custom date ranges
- Skips PRs that already have complexity labels

**Manual Trigger:**

You can trigger the workflow manually from the GitHub Actions tab with the following parameters:
- `org`: GitHub organization name (required)
- `since`: Start date (YYYY-MM-DD), defaults to yesterday
- `until`: End date (YYYY-MM-DD), defaults to same as start date
- `force`: Re-analyze PRs even if already labeled

**Required Secrets:**
- `ORG_GITHUB_TOKEN`: GitHub PAT with repo access across the organization
- `OPENAI_API_KEY`: OpenAI API key (when using `--provider openai`, default)
- `ANTHROPIC_API_KEY`: Anthropic API key (when using `--provider anthropic`)

**Optional Variables:**
- `COMPLEXITY_ORG`: Default organization (or pass via manual trigger input)
- `COMPLEXITY_PROVIDER`: Default LLM provider (`openai`, `anthropic`, or `bedrock`)

### Single PR Analysis in CI

You can also use the CLI in your own workflows to analyze PRs on events like `pull_request`:

```yaml
- name: Analyze PR Complexity
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: |
    pip install -e .
    complexity-cli label-pr
```

When run in a GitHub Actions context without a PR URL argument, the CLI automatically detects the PR from the workflow event.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black cli tests

# Lint
ruff check cli tests
```