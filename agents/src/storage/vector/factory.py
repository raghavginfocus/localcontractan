"""
Vector Store Factory

Factory for creating vector store instances based on configuration.
"""

from typing import Dict, Type

from storage.vector.base import VectorStore
from storage.vector.milvus_store import MilvusStore


class VectorStoreFactory:
    """
    Factory for creating vector store instances.
    
    Usage:
        store = VectorStoreFactory.create_store("milvus", settings)
    """

    _stores: Dict[str, Type[VectorStore]] = {
        "milvus": MilvusStore,
    }

    @classmethod
    def create_store(cls, store_name: str, settings=None) -> VectorStore:
        """
        Create a vector store instance by name.
        
        Args:
            store_name: Name of the store (e.g., "milvus")
            settings: Optional Settings instance
            
        Returns:
            VectorStore instance
            
        Raises:
            ValueError: If store name is not recognized
        """
        store_name_lower = store_name.lower()
        store_class = cls._stores.get(store_name_lower)

        if not store_class:
            available = ", ".join(cls._stores.keys())
            raise ValueError(
                f"Unknown vector store: '{store_name}'. "
                f"Available stores: {available}"
            )

        return store_class(settings=settings)

    @classmethod
    def register_store(cls, name: str, store_class: Type[VectorStore]):
        """
        Register a new vector store (for extensibility).
        
        Args:
            name: Store name identifier
            store_class: Store class implementing VectorStore
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


def create_vector_store(store_name: str, settings=None) -> VectorStore:
    """
    Convenience function to create a vector store.
    
    Args:
        store_name: Name of the store
        settings: Optional Settings instance
        
    Returns:
        VectorStore instance
    """
    return VectorStoreFactory.create_store(store_name, settings)
