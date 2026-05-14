"""
LLM Provider Factory

Factory for creating LLM provider instances based on configuration.
"""

from typing import Dict, Type

from llm.providers.base import LLMProvider
from llm.providers.ollama_provider import OllamaProvider
from llm.providers.watsonx_provider import WatsonXProvider


class LLMProviderFactory:
    """
    Factory for creating LLM providers.
    
    Usage:
        provider = LLMProviderFactory.create_provider("ollama")
        llm = provider.create_chat_model(settings)
    """

    _providers: Dict[str, Type[LLMProvider]] = {
        "ollama": OllamaProvider,
        "watsonx": WatsonXProvider
    }

    @classmethod
    def create_provider(cls, provider_name: str) -> LLMProvider:
        """
        Create a provider instance by name.
        
        Args:
            provider_name: Name of the provider (e.g., "ollama", "watsonx")
            
        Returns:
            LLMProvider instance
            
        Raises:
            ValueError: If provider name is not recognized
        """
        provider_name_lower = provider_name.lower()
        provider_class = cls._providers.get(provider_name_lower)
        
        if not provider_class:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown LLM provider: '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        return provider_class()

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[LLMProvider]):
        """
        Register a new provider (for extensibility).
        
        Args:
            name: Provider name identifier
            provider_class: Provider class implementing LLMProvider
        """
        cls._providers[name.lower()] = provider_class

    @classmethod
    def list_providers(cls) -> list[str]:
        """
        List all registered provider names.
        
        Returns:
            List of provider names
        """
        return list(cls._providers.keys())

    @classmethod
    def is_provider_available(cls, provider_name: str) -> bool:
        """
        Check if a provider is registered.
        
        Args:
            provider_name: Provider name to check
            
        Returns:
            True if provider is available, False otherwise
        """
        return provider_name.lower() in cls._providers


def create_llm_provider(provider_name: str) -> LLMProvider:
    """
    Convenience function to create an LLM provider.
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        LLMProvider instance
    """
    return LLMProviderFactory.create_provider(provider_name)
