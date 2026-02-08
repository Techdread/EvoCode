"""OpenRouter LLM provider - Access to many models including free ones."""

import time
from typing import Optional
import requests

from .base import BaseLLMProvider, LLMConfig, LLMResponse

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"


def fetch_openrouter_models(
    api_key: Optional[str] = None,
    timeout: int = 15,
    free_only: bool = False,
    provider_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict]:
    """
    Fetch available models from OpenRouter.

    Args:
        api_key: Optional API key
        timeout: Request timeout in seconds
        free_only: If True, only return free models
        provider_filter: Filter by provider (e.g., "meta-llama", "google", "anthropic")
        search: Search string to filter model names

    Returns:
        List of model dicts with 'id', 'name', 'pricing', 'context_length', etc.
    """
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(
            f"{OPENROUTER_API_URL}/models",
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        models = data.get("data", [])

        # Apply filters
        filtered = []
        for m in models:
            model_id = m.get("id", "")

            # Free filter
            if free_only:
                pricing = m.get("pricing", {})
                prompt_cost = float(pricing.get("prompt", "1") or "1")
                completion_cost = float(pricing.get("completion", "1") or "1")
                if prompt_cost != 0 or completion_cost != 0:
                    continue

            # Provider filter
            if provider_filter:
                if not model_id.lower().startswith(provider_filter.lower()):
                    continue

            # Search filter
            if search:
                search_lower = search.lower()
                name = m.get("name", "").lower()
                if search_lower not in model_id.lower() and search_lower not in name:
                    continue

            filtered.append(m)

        return filtered

    except requests.RequestException as e:
        print(f"Error fetching OpenRouter models: {e}")
        return []


def get_openrouter_providers(api_key: Optional[str] = None) -> list[str]:
    """Get list of unique providers from OpenRouter models."""
    models = fetch_openrouter_models(api_key)
    providers = set()
    for m in models:
        model_id = m.get("id", "")
        if "/" in model_id:
            provider = model_id.split("/")[0]
            providers.add(provider)
    return sorted(providers)


class OpenRouterProvider(BaseLLMProvider):
    """
    LLM provider for OpenRouter API.

    OpenRouter provides access to many LLMs through a unified API.
    Some models are free to use (use :free suffix or filter).

    API docs: https://openrouter.ai/docs
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"

        if config.api_key:
            self.session.headers["Authorization"] = f"Bearer {config.api_key}"

        # Optional headers for OpenRouter rankings
        self.session.headers["HTTP-Referer"] = "https://github.com/evocode"
        self.session.headers["X-Title"] = "EvoCode"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_server_defaults: bool = False,
    ) -> LLMResponse:
        """Generate response using OpenRouter's chat completions API."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
        }

        # Add temperature/max_tokens unless using server defaults
        if not use_server_defaults:
            payload["temperature"] = temperature if temperature is not None else self.config.temperature
            payload["max_tokens"] = max_tokens if max_tokens is not None else self.config.max_tokens

        start_time = time.time()
        response = self.session.post(
            f"{OPENROUTER_API_URL}/chat/completions",
            json=payload,
            timeout=120,
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
        """Check if OpenRouter is accessible."""
        try:
            response = self.session.get(
                f"{OPENROUTER_API_URL}/models",
                timeout=10,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_models(self) -> list[str]:
        """Get list of available models from OpenRouter."""
        models = fetch_openrouter_models(self.config.api_key)
        return [m.get("id", "") for m in models]

    def _extract_code(self, content: str, language: str) -> str:
        """Extract code from LLM response, handling markdown code blocks."""
        content = content.strip()

        # Try to extract from markdown code blocks
        import re
        pattern = rf"```(?:{language})?\s*\n?(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

        if matches:
            return matches[0].strip()

        # If no code blocks, return content as-is (might be raw code)
        return content
