"""Base classes for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

# Token limits
MIN_TOKENS = 256
DEFAULT_TOKENS = 2048
MAX_TOKENS = 65536  # 8192 * 8
TOKEN_STEP = 256

# Temperature limits
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0
DEFAULT_TEMPERATURE = 0.7


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: str
    endpoint: str
    model_name: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    display_name: Optional[str] = None

    def __post_init__(self):
        if self.display_name is None:
            self.display_name = f"{self.provider}/{self.model_name}"


@dataclass
class LLMResponse:
    """Response from an LLM generation request."""
    content: str
    model: str
    tokens_prompt: int = 0
    tokens_completion: int = 0
    latency_ms: int = 0
    finish_reason: str = "stop"
    raw_response: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.tokens_prompt + self.tokens_completion


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_server_defaults: bool = False,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt
            temperature: Override config temperature
            max_tokens: Override config max_tokens
            use_server_defaults: If True, don't send temp/max_tokens (use server settings)

        Returns:
            LLMResponse with generated content and metadata
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the LLM provider is available.

        Returns:
            True if provider is responding, False otherwise
        """
        pass

    def generate_code(
        self,
        prompt: str,
        language: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Generate code in a specific language.

        This is a convenience wrapper that uses a code-focused system prompt.

        Args:
            prompt: Description of the code to generate
            language: Programming language to use
            system_prompt: Optional custom system prompt

        Returns:
            Generated code as a string
        """
        if system_prompt is None:
            system_prompt = self._default_code_system_prompt(language)

        response = self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for code
        )
        return self._extract_code(response.content, language)

    def _default_code_system_prompt(self, language: str) -> str:
        """Get default system prompt for code generation."""
        return f"""You are an expert {language} programmer. Generate clean, efficient, and correct code.

Rules:
1. Output ONLY the code - no explanations, comments about the code, or markdown formatting
2. The code must be complete and runnable
3. Follow best practices for {language}
4. Handle edge cases appropriately
5. Do not include test code unless specifically asked"""

    def _extract_code(self, content: str, language: str) -> str:
        """
        Extract code from LLM response, handling markdown code blocks.

        Args:
            content: Raw LLM response
            language: Expected programming language

        Returns:
            Extracted code string
        """
        content = content.strip()

        # Try to extract from markdown code blocks
        import re

        # Match ```language or ``` followed by code
        patterns = [
            rf"```{language}\s*\n(.*?)```",  # ```python\n...\n```
            rf"```{language.lower()}\s*\n(.*?)```",
            r"```\s*\n(.*?)```",  # ```\n...\n```
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # If no code block found, return as-is (might already be clean code)
        return content
