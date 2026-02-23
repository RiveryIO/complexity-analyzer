"""LLM provider adapter with JSON schema validation and retries."""

import time
from typing import Any, Dict, Optional

from openai import OpenAI

from .constants import DEFAULT_MODEL, DEFAULT_TIMEOUT
from .llm_base import LLMError, LLMProvider
from .scoring import InvalidResponseError, parse_complexity_response

__all__ = ["LLMError", "OpenAIProvider", "create_llm_provider"]


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, timeout: float = DEFAULT_TIMEOUT):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name (e.g., "gpt-5.2", "gpt-4")
            timeout: Request timeout in seconds
        """
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    # Keep backward compatibility
    @property
    def model(self) -> str:
        """Return the model name (backward compatible)."""
        return self._model

    def analyze_complexity(
        self,
        prompt: str,
        diff_excerpt: str,
        stats_json: str,
        title: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Analyze PR complexity using OpenAI.

        Args:
            prompt: System prompt/instructions
            diff_excerpt: Formatted diff excerpt
            stats_json: JSON string with stats
            title: PR title
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries (exponential backoff)

        Returns:
            Dict with 'complexity' (int) and 'explanation' (str)

        Raises:
            LLMError: If analysis fails after retries
        """
        messages = [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": f"diff_excerpt:\n{diff_excerpt}\n\nstats_json:\n{stats_json}\n\ntitle:\n{title}",
            },
        ]

        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )

                content = response.choices[0].message.content
                if not content:
                    raise LLMError("Empty response from OpenAI")

                # Parse and validate response
                result = parse_complexity_response(content)

                # Add metadata
                result["provider"] = self.provider_name
                result["model"] = self.model_name
                result["tokens"] = response.usage.total_tokens if response.usage else None

                return result

            except InvalidResponseError as e:
                # If JSON parsing fails, try repair prompt
                if attempt < max_retries - 1:
                    repair_prompt = (
                        "The previous response was invalid. Please respond with ONLY a valid JSON object "
                        f"of the form: {{'complexity': <int 1..10>, 'explanation': '<string>'}}. "
                        f"Error: {str(e)}"
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": content if "content" in locals() else "",
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": repair_prompt,
                        }
                    )
                    time.sleep(retry_delay * (2**attempt))
                    continue
                raise LLMError(f"Failed to parse response after {max_retries} attempts: {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    # Add jitter
                    delay += (time.time() % 1) * 0.1
                    time.sleep(delay)
                    continue
                raise LLMError(f"OpenAI API error after {max_retries} attempts: {e}")

        raise LLMError(f"Failed after {max_retries} attempts")


def create_llm_provider(
    provider: str,
    *,
    openai_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    bedrock_model: Optional[str] = None,
    bedrock_region: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> LLMProvider:
    """
    Create an LLM provider based on the specified type.

    Args:
        provider: "openai" or "bedrock"
        openai_key: OpenAI API key (required for openai provider)
        model: OpenAI model name
        bedrock_model: Bedrock model ID (overrides env/config)
        bedrock_region: Bedrock region (overrides env/config)
        timeout: Request timeout in seconds

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider is unknown or required credentials missing
    """
    if provider == "bedrock":
        from .config import get_bedrock_config
        from .llm_bedrock import BedrockProvider

        region, model_id = get_bedrock_config()
        if bedrock_region:
            region = bedrock_region
        if bedrock_model:
            model_id = bedrock_model
        return BedrockProvider(region=region, model_id=model_id, timeout=timeout)
    if provider == "openai":
        if not openai_key:
            raise ValueError("OpenAI API key is required for openai provider")
        return OpenAIProvider(openai_key, model=model, timeout=timeout)
    raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'bedrock'.")
