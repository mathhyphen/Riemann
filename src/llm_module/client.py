"""Base LLM client interface and configuration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM API calls."""

    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None


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
