# How Complexity Analysis Works

This document explains the internals of the complexity analyzer: what it measures, how it processes PRs, and how you can fine-tune it for your organization.

## Overview

The complexity analyzer uses an LLM to estimate the **implementation complexity** of a GitHub pull request on a 1–10 scale. The goal is to approximate how "hard" the PR was to implement from a developer's perspective—design, implementation, and testing effort—not raw line count or operational risk.

## End-to-End Flow

```
PR URL → Fetch from GitHub → Preprocess Diff → Build Prompt → LLM Analysis → Parse & Return Score
```

### 1. Fetch PR from GitHub

- Uses the GitHub API to fetch the PR diff and metadata (title, additions, deletions, changed files)
- Supports token rotation for high-volume batch analysis
- Requires `GH_TOKEN` or `GITHUB_TOKEN` for private repos or higher rate limits

### 2. Preprocess the Diff

The raw diff is processed before being sent to the LLM:

| Step | What Happens |
|------|--------------|
| **Redaction** | Secrets (API keys, tokens, passwords), emails, and AWS/GitHub keys are replaced with `[REDACTED_SECRET]` or `[REDACTED_EMAIL]` |
| **Filtering** | Binary files, lockfiles (`package-lock.json`, `pnpm-lock.yaml`), markdown, and paths like `vendor/`, `node_modules/`, `dist/`, `build/`, `coverage/` are excluded |
| **Chunking** | Each file is limited to a configurable number of hunks (default: 2 per file) to keep the diff representative without overwhelming the context |
| **Truncation** | The combined diff is truncated to a token limit (default: 50,000 tokens) using tiktoken |
| **Stats** | Builds `additions`, `deletions`, `changedFiles`, `byExt`, `byLang`, `fileCount` from metadata and selected files |

### 3. Build the Prompt Input

The LLM receives a structured input containing:

- **PR URL and title**
- **Stats summary** (additions, deletions, changed files, file list)
- **Diff excerpt** between `--- DIFF START ---` and `--- DIFF END ---`

### 4. LLM Analysis

The LLM (OpenAI, Anthropic, or AWS Bedrock) is given:

1. **System prompt** — Instructions defining what "complexity" means and how to score
2. **User message** — The formatted diff excerpt, stats JSON, and title

The prompt instructs the model to:

- Focus on **code and logic complexity**, not line count
- Consider: non-trivial logic, modules touched, conceptual difficulty, testing effort
- Avoid conflating: large data/lockfile diffs with high complexity, operational risk with implementation difficulty

### 5. Parse Response

The LLM must respond with strict JSON:

```json
{"complexity": 5, "explanation": "Multiple modules with non-trivial control flow changes"}
```

The response is parsed, validated, and the complexity score is clamped to 1–10.

---

## What "Complexity" Means

The prompt defines complexity as **implementation effort**, not:

- Raw line count
- Operational risk (e.g., dangerous migrations)
- Deployment complexity

### Factors the LLM Considers

| Factor | Low (1–3) | Medium (4–6) | High (7–10) |
|--------|-----------|--------------|--------------|
| **Scope** | Single file, localized | Several modules/services | Cross-cutting, many components |
| **Logic** | Guard clauses, simple conditions, decorators | New abstractions, orchestration, mappings | Complex workflows, concurrency, stateful migrations |
| **Testing** | Minimal or straightforward | Moderate coverage | Broad and deep test changes |
| **Data** | Simple schema changes | Migration/ETL with mappings | Bidirectional compatibility, rollback considerations |

### Scoring Heuristic (from the prompt)

| Band | Score | Typical Characteristics |
|------|-------|-------------------------|
| Almost trivial | 1–2 | Single guard clause, config tweak, simple decorator, tiny migration |
| Small but non-trivial | 3–4 | Localized changes, simple business logic, basic mappings |
| Medium | 5–6 | Multiple modules, non-trivial orchestration, DTOs and mappings |
| Large or sophisticated | 7–8 | Cross-cutting changes, complex workflows, concurrency |
| Very complex | 9–10 | Major architectural changes, intricate migrations, distributed systems |

---

## Fine-Tuning for Your Organization

You can adapt the analyzer to your team's norms in several ways.

### 1. Custom Prompt File

Use `--prompt-file` (or `-p`) to supply your own prompt:

```bash
complexity-cli analyze-pr "https://github.com/org/repo/pull/123" --prompt-file ./prompts/org-specific.txt
```

**What to customize in the prompt:**

- **Domain-specific examples** — Add examples from your codebase (e.g., "Our ETL rivers typically involve X, Y, Z")
- **Scoring bands** — Adjust the 1–10 bands to match your team's expectations (e.g., if "medium" PRs in your org are usually 4–5, not 5–6)
- **Factors to emphasize** — E.g., "In our org, data pipeline changes are typically higher complexity due to downstream dependencies"
- **Factors to de-emphasize** — E.g., "We treat lockfile-only dependency bumps as 1 regardless of size"
- **Output format** — The prompt must still instruct the LLM to return `{"complexity": N, "explanation": "..."}`

**Example custom prompt addition** (append to the default or use as a base):

```
------------------------------------------------------------
ORGANIZATION-SPECIFIC GUIDANCE
------------------------------------------------------------

For [YourOrg]:
- Data pipeline / river changes: Add +1 to base score if multiple sources or targets are involved.
- Infra/DevOps PRs: Treat Terraform/K8s changes as moderate (4–6) when touching multiple environments.
- Frontend-only PRs: UI-only changes without new logic are typically 2–4.
```

### 2. Adjust Diff Processing

| Option | Default | Purpose |
|--------|---------|---------|
| `--max-tokens` | 50000 | Increase if your PRs are large and you want more context; decrease to reduce cost/latency |
| `--hunks-per-file` | 2 | Increase to show more of each file (e.g., 3–4 for refactors); decrease for very large PRs |

```bash
complexity-cli analyze-pr "https://github.com/org/repo/pull/123" --max-tokens 80000 --hunks-per-file 3
```

### 3. Filter and Ignore Patterns

To exclude more file types or paths, you would need to modify `cli/preprocess.py`:

- `IGNORE_EXT_RE` — File extensions to skip (e.g., add `.snap` for Jest snapshots)
- `IGNORE_PATH_RE` — Path patterns (e.g., add `generated/` or `__fixtures__/`)

### 4. Velocity Weighting

The README suggests t-shirt sizes for velocity:

| Score | Size | Weight |
|-------|------|--------|
| 1–2 | XS | 0 |
| 3 | S | 1 |
| 4 | M | 2 |
| 5–6 | L | 3 |
| 7+ | XL | 4 |

You can change these weights in your reporting/BI layer to match how your org values different PR sizes.

### 5. Calibration with Historical PRs

1. Run batch analysis on a sample of closed PRs:
   ```bash
   complexity-cli batch-analyze --org yourorg --since 2024-01-01 --until 2024-01-31 --output calibration.csv
   ```
2. Manually review a subset and note where scores feel off.
3. Update your custom prompt with guidance that corrects those cases.
4. Re-run and compare until the distribution matches your expectations.

---

## Configuration Reference

| Config | Default | Description |
|--------|---------|-------------|
| `max_tokens` | 50000 | Max tokens for diff excerpt |
| `hunks_per_file` | 2 | Max hunks per file in excerpt |
| `model` | gpt-5.2 | LLM model (provider-specific) |
| `timeout` | 120 | Request timeout (seconds) |
| `provider` | openai | `openai`, `anthropic`, or `bedrock` |
| `prompt_file` | (embedded) | Path to custom prompt |

---

## File Layout

| File | Role |
|------|------|
| `cli/analyze.py` | Core analysis flow: fetch → process → LLM → parse |
| `cli/preprocess.py` | Redaction, filtering, chunking, truncation, stats |
| `cli/prompt/default.txt` | Default LLM prompt (scoring rules, factors, examples) |
| `cli/scoring.py` | Parse LLM JSON response, validate, clamp score |
| `cli/llm*.py` | Provider implementations (OpenAI, Anthropic, Bedrock) |
