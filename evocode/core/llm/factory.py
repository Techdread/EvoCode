"""Factory for creating LLM providers."""

from typing import Type

from .base import BaseLLMProvider, LLMConfig
from .lmstudio import LMStudioProvider
from .openrouter import OpenRouterProvider


# Registry of available providers
_PROVIDERS: dict[str, Type[BaseLLMProvider]] = {
    "lmstudio": LMStudioProvider,
    "openai": LMStudioProvider,  # OpenAI-compatible, works with LM Studio
    "local": LMStudioProvider,   # Alias for local models
    "openrouter": OpenRouterProvider,
}


def register_provider(name: str, provider_class: Type[BaseLLMProvider]):
    """Register a new LLM provider."""
    _PROVIDERS[name.lower()] = provider_class


def get_available_providers() -> list[str]:
    """Get list of available provider names."""
    return list(_PROVIDERS.keys())


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    """
    Create an LLM provider from configuration.

    Args:
        config: LLMConfig with provider details

    Returns:
        Instance of the appropriate BaseLLMProvider subclass

    Raises:
        ValueError: If provider is not supported
    """
    provider_name = config.provider.lower()

    if provider_name not in _PROVIDERS:
        available = ", ".join(get_available_providers())
        raise ValueError(f"Unknown provider: {config.provider}. Available: {available}")

    provider_class = _PROVIDERS[provider_name]
    return provider_class(config)


def create_provider_from_dict(data: dict) -> BaseLLMProvider:
    """
    Create an LLM provider from a dictionary.

    Useful for creating providers from database records or config files.

    Args:
        data: Dictionary with provider configuration

    Returns:
        Instance of the appropriate BaseLLMProvider subclass
    """
    config = LLMConfig(
        provider=data.get("provider", "lmstudio"),
        endpoint=data.get("endpoint", "http://localhost:1234/v1"),
        model_name=data.get("model_name", "default"),
        api_key=data.get("api_key"),
        temperature=data.get("temperature", 0.7),
        max_tokens=data.get("max_tokens", 2048),
        display_name=data.get("display_name"),
    )
    return create_provider(config)
