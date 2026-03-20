"""Anthropic Claude client implementation."""

import logging
import os
from typing import Any, Generator, Optional

from .client import LLMClient, LLMConfig, LLMResponse
from . import register_llm_client

logger = logging.getLogger(__name__)


@register_llm_client("anthropic")
class AnthropicClient(LLMClient):
    """Client for Anthropic Claude API.

    This client provides access to Claude models through the Anthropic API.
    Supports both synchronous and streaming generation.
    """

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize Anthropic client.

        Args:
            config: LLM configuration (optional)
        """
        self.config = config or LLMConfig()
        self._api_key = self._get_api_key()
        self._base_url = self.config.api_endpoint or os.environ.get("ANTHROPIC_BASE_URL")
        self._client = None

    def _get_api_key(self) -> str:
        """Get API key from environment variable.

        Returns:
            API key string

        Raises:
            ValueError: If API key is not set
        """
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please set it in your .env file or environment."
            )
        return api_key

    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                client_kwargs = {"api_key": self._api_key}
                if self._base_url:
                    client_kwargs["base_url"] = self._base_url
                self._client = anthropic.Anthropic(**client_kwargs)
            except ImportError:
                raise ImportError(
                    "anthropic package is required. "
                    "Install it with: pip install anthropic"
                )
        return self._client

    def _extract_text_content(self, response: Any) -> str:
        """Extract user-visible text from heterogeneous content blocks."""

        content_parts = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                content_parts.append(text)

        return "\n".join(content_parts).strip()

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model name (overrides config)
            temperature: Sampling temperature (overrides config)
            max_tokens: Max tokens to generate (overrides config)
            **kwargs: Additional arguments

        Returns:
            LLMResponse object
        """
        model = model or self.config.model or self.DEFAULT_MODEL
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
                **kwargs,
            )

            content = self._extract_text_content(response)

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=response.stop_reason,
                raw_response=response.model_dump(),
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Generate a streaming response from Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model name (overrides config)
            temperature: Sampling temperature (overrides config)
            max_tokens: Max tokens to generate (overrides config)
            **kwargs: Additional arguments

        Yields:
            Chunks of the generated response
        """
        model = model or self.config.model or self.DEFAULT_MODEL
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        messages = [{"role": "user", "content": prompt}]

        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
                **kwargs,
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            logger.error(f"Anthropic streaming API error: {e}")
            raise

    def get_model_name(self) -> str:
        """Get the current model name.

        Returns:
            Model name string
        """
        return self.config.model or self.DEFAULT_MODEL
