"""
LLM Provider Abstraction Layer

This module provides a clean abstraction for LLM providers, allowing easy
swapping between different providers (Ollama, WatsonX, etc.) without modifying
agent code.

Currently supported:
- Ollama: Active and ready to use
- WatsonX: Prepared for future integration (see watsonx_provider.py)
"""

from llm.provider_factory import LLMProviderFactory, create_llm_provider

__all__ = ["LLMProviderFactory", "create_llm_provider"]
