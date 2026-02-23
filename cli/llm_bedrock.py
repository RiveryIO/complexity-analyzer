"""AWS Bedrock LLM provider adapter."""

import json
import time
from typing import Any, Dict, Optional

import boto3

from .constants import DEFAULT_BEDROCK_MODEL, DEFAULT_TIMEOUT
from .llm_base import LLMError, LLMProvider
from .scoring import InvalidResponseError, parse_complexity_response


class BedrockProvider(LLMProvider):
    """AWS Bedrock provider implementation using Converse API."""

    COMPLEXITY_SCHEMA = {
        "type": "object",
        "properties": {
            "complexity": {
                "type": "integer",
                "description": "Complexity score from 1 (low) to 10 (high)",
            },
            "explanation": {
                "type": "string",
                "description": "Brief explanation of the complexity score",
            },
        },
        "required": ["complexity", "explanation"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        region: str,
        model_id: str = DEFAULT_BEDROCK_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
        profile_name: Optional[str] = None,
    ):
        """
        Initialize Bedrock provider.

        Args:
            region: AWS region (e.g., "us-east-1")
            model_id: Bedrock model ID (e.g., "anthropic.claude-sonnet-4-5-20250929-v1:0")
            timeout: Request timeout in seconds
            profile_name: Optional AWS profile name (uses AWS_PROFILE env if not set)
        """
        kwargs: Dict[str, Any] = {"service_name": "bedrock-runtime", "region_name": region}
        if profile_name:
            kwargs["profile_name"] = profile_name
        self.client = boto3.client(**kwargs)
        self._model = model_id
        self._region = region
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "bedrock"

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
        Analyze PR complexity using AWS Bedrock.

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
        user_content = (
            f"diff_excerpt:\n{diff_excerpt}\n\nstats_json:\n{stats_json}\n\ntitle:\n{title}"
        )

        messages = [
            {"role": "user", "content": [{"text": user_content}]},
        ]

        for attempt in range(max_retries):
            try:
                response = self.client.converse(
                    modelId=self._model,
                    messages=messages,
                    system=[{"text": prompt}],
                    inferenceConfig={
                        "maxTokens": 2048,
                        "temperature": 0.0,
                    },
                    outputConfig={
                        "textFormat": {
                            "type": "json_schema",
                            "structure": {
                                "jsonSchema": {
                                    "schema": json.dumps(self.COMPLEXITY_SCHEMA),
                                    "name": "complexity_response",
                                    "description": "PR complexity analysis result",
                                }
                            },
                        }
                    },
                )

                content = self._extract_content(response)
                if not content:
                    raise LLMError("Empty response from Bedrock")

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
                        {
                            "role": "assistant",
                            "content": [{"text": content if "content" in locals() else ""}],
                        }
                    )
                    messages.append(
                        {"role": "user", "content": [{"text": repair_prompt}]},
                    )
                    time.sleep(retry_delay * (2**attempt))
                    continue
                raise LLMError(f"Failed to parse response after {max_retries} attempts: {e}")

            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    delay += (time.time() % 1) * 0.1
                    time.sleep(delay)
                    continue
                raise LLMError(f"Bedrock API error after {max_retries} attempts: {e}")

        raise LLMError(f"Failed after {max_retries} attempts")

    def _extract_content(self, response: Dict[str, Any]) -> str:
        """Extract text content from Converse API response."""
        try:
            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            for block in content_blocks:
                if "text" in block:
                    return block["text"].strip()
        except (KeyError, TypeError, AttributeError):
            pass
        return ""

    def _extract_tokens(self, response: Dict[str, Any]) -> Optional[int]:
        """Extract token usage from Converse API response."""
        try:
            usage = response.get("usage", {})
            return usage.get("totalTokens") or (
                (usage.get("inputTokens", 0) or 0) + (usage.get("outputTokens", 0) or 0)
            )
        except (KeyError, TypeError):
            return None
