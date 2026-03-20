"""OpenAI API client implementation."""

import logging
import os
from typing import Any, Generator, Optional

from .client import LLMClient, LLMConfig, LLMResponse
from . import register_llm_client

logger = logging.getLogger(__name__)


@register_llm_client("openai")
class OpenAIClient(LLMClient):
    """OpenAI GPT API client."""

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize OpenAI client.

        Args:
            config: LLM configuration
        """
        self.config = config or LLMConfig()
        self._api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        self._base_url = self.config.api_endpoint or os.environ.get("OPENAI_BASE_URL")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate response from OpenAI GPT.

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
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        client_kwargs = {"api_key": self._api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url
        client = OpenAI(**client_kwargs)

        model = model or self.config.model or self.DEFAULT_MODEL
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        choice = response.choices[0]
        content = choice.message.content or ""

        return LLMResponse(
            content=content,
            model=model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=choice.finish_reason,
            raw_response=response.model_dump(),
        )

    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Generate streaming response from OpenAI GPT.

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
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        client_kwargs = {"api_key": self._api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url
        client = OpenAI(**client_kwargs)

        model = model or self.config.model or self.DEFAULT_MODEL
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_model_name(self) -> str:
        """Get the current model name.

        Returns:
            Model name string
        """
        return self.config.model or self.DEFAULT_MODEL
