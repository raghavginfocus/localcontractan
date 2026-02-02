"""
Storage Abstraction Layer

This module provides abstractions for storage backends (SPARQL stores, vector stores, etc.),
allowing easy swapping between different implementations without modifying agent code.
"""

from storage.sparql.factory import SPARQLStoreFactory, create_sparql_store
from storage.vector.factory import VectorStoreFactory, create_vector_store

__all__ = [
    "SPARQLStoreFactory",
    "create_sparql_store",
    "VectorStoreFactory",
    "create_vector_store",
]
