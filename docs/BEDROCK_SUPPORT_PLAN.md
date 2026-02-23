# AWS Bedrock Support Plan

## Overview

Add AWS Bedrock as an alternative LLM provider alongside OpenAI. Bedrock uses IAM credentials (via AWS profile) instead of API keys.

## Current Architecture

- **`cli/llm_base.py`**: Abstract `LLMProvider` with `analyze_complexity()` interface
- **`cli/llm.py`**: `OpenAIProvider` implementing the interface
- **`cli/main.py`**: Hardcodes `OpenAIProvider` in `analyze_pr_to_dict()`
- **`cli/config.py`**: `get_openai_api_key()` for credentials
- **`cli/constants.py`**: `DEFAULT_MODEL` (gpt-5.2)

## Implementation Plan

### 1. Add Dependencies

In `pyproject.toml`:

```toml
dependencies = [
    ...
    "boto3>=1.34.0",  # AWS SDK for Bedrock
]
```

### 2. Create Bedrock Provider

**New file: `cli/llm_bedrock.py`**

- Implement `BedrockProvider(LLMProvider)` using `boto3.client("bedrock-runtime")`
- Use Converse API or InvokeModel (Messages format) for chat completion
- Map OpenAI-style messages to Bedrock format
- Support JSON response via `response_format` / `inferenceConfig`
- Default model: `anthropic.claude-sonnet-4-5-20250929-v1:0` (Claude Sonnet 4.5)
- Use `AWS_PROFILE` and `AWS_REGION` from env (or `BEDROCK_REGION` override)

### 3. Config Updates

**`cli/config.py`**:

- Add `get_bedrock_config() -> tuple[str, str] | None` returning `(region, model_id)` or None
- Read `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION` from env

**`cli/config_types.py`**:

- Add `provider: Literal["openai", "bedrock"]` to `AnalysisConfig`
- Add `bedrock_model: Optional[str]` and `bedrock_region: Optional[str]`

**`env.example`** (and `.env`):

```
# AWS Bedrock (optional - use instead of OpenAI)
# Set AWS_PROFILE or use: source ~/Documents/productivity/bash_methods_boomi.sh && bedrock_env
AWS_PROFILE=boomi-knowledge-hub-dev
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
```

### 4. Provider Factory

**New/updated: `cli/llm.py` or `cli/llm_factory.py`**

```python
def create_llm_provider(
    provider: str,
    *,
    openai_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    bedrock_model: Optional[str] = None,
    bedrock_region: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> LLMProvider:
    if provider == "bedrock":
        return BedrockProvider(region=..., model_id=..., timeout=...)
    return OpenAIProvider(openai_key, model=model, timeout=timeout)
```

### 5. Main / Analyze Integration

**`cli/main.py`**:

- Add `--provider` option: `openai` | `bedrock` (default: `openai`)
- Add `--bedrock-model` option for Bedrock model ID
- In `analyze_pr_to_dict()`: replace hardcoded `OpenAIProvider` with `create_llm_provider(provider, ...)`
- Credential logic: if `provider == "bedrock"`, skip `OPENAI_API_KEY` check; require `AWS_PROFILE` or default credentials

**`cli/analyze.py`**:

- Update `analyze_single_pr()` to accept provider and use factory

### 6. Batch & Label Commands

- Add `--provider` and `--bedrock-model` to `batch-analyze` and `label-pr`
- Pass provider through to `analyze_fn` / `analyze_pr_to_dict`

### 7. Tests

- **`tests/test_llm_bedrock.py`**: Mock `boto3.client`; test `BedrockProvider.analyze_complexity()` success, empty response, invalid JSON, retries
- **`tests/test_config.py`**: Add tests for `get_bedrock_config()`
- **`tests/test_cli.py`**: Add integration tests for `--provider bedrock` (mocked)

### 8. Documentation

- Update README with Bedrock setup (profile, region, model)
- Document `bedrock_env` alias in `bash_methods_boomi.sh`

## Usage (After Implementation)

```bash
# Set Bedrock env (profile + region)
source ~/Documents/productivity/bash_methods_boomi.sh
bedrock_env

# Analyze with Bedrock
complexity-cli analyze-pr https://github.com/owner/repo/pull/123 --provider bedrock

# Or with explicit model
complexity-cli analyze-pr <URL> --provider bedrock --bedrock-model anthropic.claude-sonnet-4-5-20250929-v1:0
```

## Bash Helper (Already Added)

In `~/Documents/productivity/bash_methods_boomi.sh`:

```bash
alias bedrock_env="export AWS_PROFILE=boomi-knowledge-hub-dev && export AWS_REGION=us-east-1"
```

Run `bedrock_env` before using `--provider bedrock`.

## File Checklist

| File | Action |
|------|--------|
| `pyproject.toml` | Add boto3 |
| `cli/llm_bedrock.py` | Create BedrockProvider |
| `cli/llm.py` or new `cli/llm_factory.py` | Add create_llm_provider() |
| `cli/config.py` | Add get_bedrock_config() |
| `cli/config_types.py` | Add provider, bedrock fields |
| `cli/main.py` | Add --provider, --bedrock-model, use factory |
| `cli/analyze.py` | Use provider in analyze_single_pr |
| `cli/batch.py` | Pass provider through (if needed) |
| `env.example` | Add Bedrock vars |
| `tests/test_llm_bedrock.py` | New tests |
| `tests/test_config.py` | Bedrock config tests |
| `README.md` | Bedrock setup docs |
