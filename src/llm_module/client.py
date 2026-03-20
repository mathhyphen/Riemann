"""Base LLM client interface and configuration."""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM API calls."""

    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None


def resolve_llm_config(provider: Optional[str] = None) -> LLMConfig:
    """Build an LLM configuration from environment variables."""

    provider_name = provider or os.environ.get("LLM_PROVIDER")
    endpoint = os.environ.get("LLM_API_ENDPOINT")

    if not endpoint and provider_name == "openai":
        endpoint = os.environ.get("OPENAI_BASE_URL")
    if not endpoint and provider_name == "anthropic":
        endpoint = os.environ.get("ANTHROPIC_BASE_URL")
    if not endpoint and provider_name == "minimax":
        endpoint = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")

    api_key = os.environ.get("LLM_API_KEY")
    if not api_key and provider_name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key and provider_name == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and provider_name == "minimax":
        api_key = os.environ.get("MINIMAX_API_KEY")

    temperature_raw = os.environ.get("LLM_TEMPERATURE")
    max_tokens_raw = os.environ.get("LLM_MAX_TOKENS")

    return LLMConfig(
        model=os.environ.get("LLM_MODEL"),
        temperature=float(temperature_raw) if temperature_raw else 0.7,
        max_tokens=int(max_tokens_raw) if max_tokens_raw else 4096,
        api_endpoint=endpoint,
        api_key=api_key,
    )


@dataclass(frozen=True)
class LLMResponse:
    """Response structure from LLM API."""

    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class LLMClient(ABC):
    """Abstract base class for LLM clients.

    This class defines the interface for interacting with various
    language model providers (Anthropic, OpenAI, etc.).
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model name (overrides config)
            temperature: Sampling temperature (overrides config)
            max_tokens: Max tokens to generate (overrides config)
            **kwargs: Additional provider-specific arguments

        Returns:
            LLMResponse object with content and metadata
        """
        pass

    @abstractmethod
    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Generate a streaming response from the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model name (overrides config)
            temperature: Sampling temperature (overrides config)
            max_tokens: Max tokens to generate (overrides config)
            **kwargs: Additional provider-specific arguments

        Yields:
            Chunks of the generated response
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name.

        Returns:
            Model name string
        """
        pass
