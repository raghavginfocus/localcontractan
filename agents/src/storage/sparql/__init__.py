"""
SPARQL Store Abstraction

Abstract interface for SPARQL-compatible graph databases.
"""

from storage.sparql.base import SPARQLStore
from storage.sparql.fuseki_store import FusekiStore
from storage.sparql.factory import SPARQLStoreFactory, create_sparql_store

__all__ = [
    "SPARQLStore",
    "FusekiStore",
    "SPARQLStoreFactory",
    "create_sparql_store",
]
