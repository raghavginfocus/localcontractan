"""
Storage Abstraction Layer

This module provides abstractions for storage backends (SPARQL stores, vector stores,
object storage), allowing easy swapping between different implementations.
"""

from storage.sparql.factory import SPARQLStoreFactory, create_sparql_store
from storage.vector.factory import VectorStoreFactory, create_vector_store
from storage.object_storage import (
    ObjectStorageBackend,
    create_object_storage,
    get_object_storage_from_config,
)

__all__ = [
    "SPARQLStoreFactory",
    "create_sparql_store",
    "VectorStoreFactory",
    "create_vector_store",
    "ObjectStorageBackend",
    "create_object_storage",
    "get_object_storage_from_config",
]
