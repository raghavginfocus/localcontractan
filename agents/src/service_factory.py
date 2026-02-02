"""
Service Factory for Dependency Injection

This module provides a centralized factory for creating and managing
service instances, enabling dependency injection throughout the application.
"""

from config import Settings, get_settings
from storage.sparql.factory import SPARQLStoreFactory
from storage.vector.factory import VectorStoreFactory
from llm.provider_factory import LLMProviderFactory
from logger.factory import LoggerFactory
from logger.base import BaseLogger  # noqa: E402


class ServiceFactory:
    """
    Centralized factory for creating service instances.
    
    This enables dependency injection by providing a single place to create
    and configure services, making it easy to swap implementations or inject mocks.
    """

    def __init__(self, settings: Settings | None = None):
        """
        Initialize the service factory.
        
        Args:
            settings: Application settings (defaults to get_settings())
        """
        self.settings = settings or get_settings()
        self._sparql_store = None
        self._vector_store = None

    def get_sparql_store(self):
        """
        Get or create SPARQL store instance (singleton per factory).
        
        Returns:
            SPARQLStore instance
        """
        if self._sparql_store is None:
            store_name = self.settings.sparql_store
            self._sparql_store = SPARQLStoreFactory.create_store(
                store_name, settings=self.settings
            )
        return self._sparql_store

    def get_vector_store(self):
        """
        Get or create vector store instance (singleton per factory).
        
        Returns:
            VectorStore instance
        """
        if self._vector_store is None:
            store_name = self.settings.vector_store
            self._vector_store = VectorStoreFactory.create_store(
                store_name, settings=self.settings
            )
        return self._vector_store

    def create_llm_provider(self):
        """
        Create LLM provider instance.
        
        Returns:
            LLMProvider instance
        """
        provider_name = self.settings.llm_provider
        return LLMProviderFactory.create_provider(provider_name)
    
    def get_logger(self, module_name: str, **kwargs) -> BaseLogger:
        """
        Get or create a logger instance for a module.
        
        Args:
            module_name: Name of the module (e.g., "graph_manager")
            **kwargs: Additional logger configuration options
            
        Returns:
            BaseLogger instance
        """
        # Get log level from settings if available
        log_level = getattr(self.settings, "log_level", "INFO")
        enable_json = getattr(self.settings, "log_json_format", False)
        
        return LoggerFactory.create_logger(
            module_name=module_name,
            log_level=log_level,
            enable_json=enable_json,
            settings=self.settings,
            **kwargs
        )


# Global factory instance (can be overridden for testing)
_global_factory: ServiceFactory | None = None


def get_service_factory(settings: Settings | None = None) -> ServiceFactory:
    """
    Get the global service factory instance.
    
    Args:
        settings: Optional settings to use (only used on first call)
        
    Returns:
        ServiceFactory instance
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = ServiceFactory(settings=settings)
    return _global_factory


def set_service_factory(factory: ServiceFactory) -> None:
    """
    Set a custom service factory (useful for testing).
    
    Args:
        factory: ServiceFactory instance to use
    """
    global _global_factory
    _global_factory = factory
