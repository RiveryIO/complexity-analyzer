"""Anthropic API LLM provider adapter."""

import time
from typing import Any, Dict, Optional

import anthropic

from .constants import DEFAULT_ANTHROPIC_MODEL, DEFAULT_TIMEOUT
from .llm_base import LLMError, LLMProvider
from .scoring import InvalidResponseError, parse_complexity_response


class AnthropicProvider(LLMProvider):
    """Anthropic API provider implementation."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (e.g., "claude-sonnet-4-5-20250929", "claude-3-5-sonnet-20241022")
            timeout: Request timeout in seconds
        """
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self._model = model
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "anthropic"

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

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
        Analyze PR complexity using Anthropic API.

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
        json_instruction = (
            "\n\nRespond with ONLY a valid JSON object: "
            '{"complexity": <int 1-10>, "explanation": "<string>"}'
        )
        user_content = (
            f"diff_excerpt:\n{diff_excerpt}\n\nstats_json:\n{stats_json}\n\ntitle:\n{title}"
        )

        messages = [{"role": "user", "content": user_content}]

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self._model,
                    max_tokens=2048,
                    system=prompt + json_instruction,
                    messages=messages,
                    temperature=0.0,
                )

                content = self._extract_content(response)
                if not content:
                    raise LLMError("Empty response from Anthropic")

                result = parse_complexity_response(content)

                result["provider"] = self.provider_name
                result["model"] = self.model_name
                result["tokens"] = self._extract_tokens(response)

                return result

            except InvalidResponseError as e:
                if attempt < max_retries - 1:
                    repair_prompt = (
                        "The previous response was invalid. Please respond with ONLY a valid JSON object "
                        f"of the form: {{'complexity': <int 1..10>, 'explanation': '<string>'}}. "
                        f"Error: {str(e)}"
                    )
                    messages.append(
                        {"role": "assistant", "content": content if "content" in locals() else ""}
                    )
                    messages.append({"role": "user", "content": repair_prompt})
                    time.sleep(retry_delay * (2**attempt))
                    continue
                raise LLMError(f"Failed to parse response after {max_retries} attempts: {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    delay += (time.time() % 1) * 0.1
                    time.sleep(delay)
                    continue
                raise LLMError(f"Anthropic API error after {max_retries} attempts: {e}")

        raise LLMError(f"Failed after {max_retries} attempts")

    def _extract_content(self, response: Any) -> str:
        """Extract text content from Anthropic message response."""
        try:
            if response.content and len(response.content) > 0:
                block = response.content[0]
                if hasattr(block, "text"):
                    return block.text.strip()
        except (AttributeError, IndexError, TypeError):
            pass
        return ""

    def _extract_tokens(self, response: Any) -> Optional[int]:
        """Extract token usage from Anthropic response."""
        try:
            if response.usage:
                inp = getattr(response.usage, "input_tokens", 0) or 0
                out = getattr(response.usage, "output_tokens", 0) or 0
                return inp + out
        except (AttributeError, TypeError):
            pass
        return None
