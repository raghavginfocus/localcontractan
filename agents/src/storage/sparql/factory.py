"""
SPARQL Store Factory

Factory for creating SPARQL store instances based on configuration.
"""

from typing import Dict, Type

from storage.sparql.base import SPARQLStore
from storage.sparql.fuseki_store import FusekiStore


class SPARQLStoreFactory:
    """
    Factory for creating SPARQL store instances.
    
    Usage:
        store = SPARQLStoreFactory.create_store("fuseki", settings)
    """

    _stores: Dict[str, Type[SPARQLStore]] = {
        "fuseki": FusekiStore,
    }

    @classmethod
    def create_store(cls, store_name: str, settings=None) -> SPARQLStore:
        """
        Create a SPARQL store instance by name.
        
        Args:
            store_name: Name of the store (e.g., "fuseki")
            settings: Optional Settings instance
            
        Returns:
            SPARQLStore instance
            
        Raises:
            ValueError: If store name is not recognized
        """
        store_name_lower = store_name.lower()
        store_class = cls._stores.get(store_name_lower)

        if not store_class:
            available = ", ".join(cls._stores.keys())
            raise ValueError(
                f"Unknown SPARQL store: '{store_name}'. "
                f"Available stores: {available}"
            )

        return store_class(settings=settings)

    @classmethod
    def register_store(cls, name: str, store_class: Type[SPARQLStore]):
        """
        Register a new SPARQL store (for extensibility).
        
        Args:
            name: Store name identifier
            store_class: Store class implementing SPARQLStore
        """
        cls._stores[name.lower()] = store_class

    @classmethod
    def list_stores(cls) -> list[str]:
        """List all registered store names."""
        return list(cls._stores.keys())

    @classmethod
    def is_store_available(cls, store_name: str) -> bool:
        """Check if a store is registered."""
        return store_name.lower() in cls._stores


def create_sparql_store(store_name: str, settings=None) -> SPARQLStore:
    """
    Convenience function to create a SPARQL store.
    
    Args:
        store_name: Name of the store
        settings: Optional Settings instance
        
    Returns:
        SPARQLStore instance
    """
    return SPARQLStoreFactory.create_store(store_name, settings)
