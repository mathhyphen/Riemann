"""LLM module for interacting with various language model providers."""

# ruff: noqa: E402

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


from .client import LLMClient, LLMConfig, LLMResponse, resolve_llm_config
from .anthropic_client import AnthropicClient
from .openai_client import OpenAIClient
from .prompt_builder import ProofPromptBuilder

__all__ = [
    "LLMClient",
    "LLMConfig",
    "LLMResponse",
    "resolve_llm_config",
    "AnthropicClient",
    "OpenAIClient",
    "LLMFactory",
    "register_llm_client",
    "ProofPromptBuilder",
]
