"""
Base LLM Provider Interface

Abstract base class defining the interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from langchain_core.language_models import BaseChatModel

from config import Settings


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers must implement this interface to ensure consistent
    behavior across different services (OpenAI, Ollama, Anthropic, WatsonX, etc.).
    """

    @abstractmethod
    def create_chat_model(self, settings: Settings, **kwargs) -> BaseChatModel:
        """
        Create a LangChain chat model instance for this provider.
        
        Args:
            settings: Application settings containing provider configuration
            **kwargs: Additional parameters (e.g., temperature, max_tokens)
            
        Returns:
            BaseChatModel instance configured for this provider
        """
        pass

    @abstractmethod
    def validate_config(self, settings: Settings) -> bool:
        """
        Validate that provider configuration is complete and valid.
        
        Args:
            settings: Application settings to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return provider capabilities and limitations.
        
        Returns:
            Dictionary with capability information:
            - supports_streaming: bool
            - supports_function_calling: bool
            - max_tokens: int (or None if unlimited)
            - supported_models: list[str]
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Provider name identifier (e.g., 'openai', 'ollama', 'watsonx').
        
        Returns:
            Provider name string
        """
        pass

    def get_health_check_url(self) -> str | None:
        """
        Optional: Return a URL to check provider health/connectivity.
        
        Returns:
            Health check URL or None if not applicable
        """
        return None
