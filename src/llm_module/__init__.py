"""LLM module for interacting with various language model providers."""

from typing import Dict, Type

LLM_CLIENTS: Dict[str, Type["LLMClient"]] = {}


def register_llm_client(name: str):
    """Decorator to register LLM clients."""
    def decorator(cls):
        LLM_CLIENTS[name] = cls
        return cls
    return decorator


def LLMFactory(name: str, **kwargs) -> "LLMClient":
    """Factory to create LLM clients."""
    client_cls = LLM_CLIENTS.get(name)
    if client_cls is None:
        raise ValueError(f"Unknown LLM client: {name}")
    return client_cls(**kwargs)


from .client import LLMClient
from .anthropic_client import AnthropicClient
from .openai_client import OpenAIClient

__all__ = [
    "LLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "LLMFactory",
    "register_llm_client",
]
