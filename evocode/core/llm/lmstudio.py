"""LM Studio OpenAI-compatible LLM provider."""

import time
from typing import Optional
import requests

from .base import BaseLLMProvider, LLMConfig, LLMResponse


def fetch_lmstudio_models(endpoint: str, timeout: int = 10) -> list[dict]:
    """
    Fetch available models from an LM Studio endpoint.

    Args:
        endpoint: LM Studio API endpoint (e.g., http://localhost:1234/v1)
        timeout: Request timeout in seconds

    Returns:
        List of model dicts with 'id' and other metadata
    """
    try:
        response = requests.get(
            f"{endpoint.rstrip('/')}/models",
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except requests.RequestException:
        return []


class LMStudioProvider(BaseLLMProvider):
    """
    LLM provider for LM Studio's OpenAI-compatible API.

    LM Studio exposes an OpenAI-compatible endpoint at /v1/chat/completions.
    Default endpoint is http://localhost:1234/v1
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.session = requests.Session()
        if config.api_key:
            self.session.headers["Authorization"] = f"Bearer {config.api_key}"
        self.session.headers["Content-Type"] = "application/json"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_server_defaults: bool = False,
    ) -> LLMResponse:
        """Generate response using LM Studio's chat completions API.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Override temperature (ignored if use_server_defaults=True)
            max_tokens: Override max tokens (ignored if use_server_defaults=True)
            use_server_defaults: If True, don't send temperature/max_tokens - use LM Studio's settings
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
        }

        # Only add temperature/max_tokens if not using server defaults
        if not use_server_defaults:
            payload["temperature"] = temperature if temperature is not None else self.config.temperature
            payload["max_tokens"] = max_tokens if max_tokens is not None else self.config.max_tokens

        start_time = time.time()
        response = self.session.post(
            f"{self.config.endpoint}/chat/completions",
            json=payload,
            timeout=120,  # Long timeout for slow models
        )
        latency_ms = int((time.time() - start_time) * 1000)

        response.raise_for_status()
        data = response.json()

        # Parse OpenAI-format response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        usage = data.get("usage", {})
        tokens_prompt = usage.get("prompt_tokens", 0)
        tokens_completion = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=content,
            model=data.get("model", self.config.model_name),
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )

    def health_check(self) -> bool:
        """Check if LM Studio is running and responding."""
        try:
            response = self.session.get(
                f"{self.config.endpoint}/models",
                timeout=5,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_models(self) -> list[str]:
        """Get list of available models from LM Studio."""
        try:
            response = self.session.get(
                f"{self.config.endpoint}/models",
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return [m.get("id", "") for m in data.get("data", [])]
        except requests.RequestException:
            return []
