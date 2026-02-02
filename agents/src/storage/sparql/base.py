"""
Base SPARQL Store Interface

Abstract base class defining the interface that all SPARQL stores must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

from rdflib import Graph


class SPARQLStore(ABC):
    """
    Abstract base class for SPARQL-compatible graph databases.
    
    This abstraction allows swapping between different SPARQL endpoints
    (Fuseki, Blazegraph, Stardog, etc.) without modifying agent code.
    """

    @abstractmethod
    def execute_select(self, query: str, add_prefixes: bool = True) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query and return results.
        
        Args:
            query: SPARQL SELECT query string
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            List of dictionaries with variable bindings
        """
        pass

    @abstractmethod
    def execute_construct(self, query: str, add_prefixes: bool = True) -> Graph:
        """
        Execute a SPARQL CONSTRUCT query and return an RDF graph.
        
        Args:
            query: SPARQL CONSTRUCT query string
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            RDF Graph with constructed triples
        """
        pass

    @abstractmethod
    def execute_update(self, update_query: str) -> bool:
        """
        Execute a SPARQL UPDATE operation (INSERT, DELETE, etc.).
        
        Args:
            update_query: SPARQL UPDATE query string
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def execute_ask(self, query: str, add_prefixes: bool = True) -> bool:
        """
        Execute a SPARQL ASK query and return boolean result.
        
        Args:
            query: SPARQL ASK query string
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            Boolean result of the ASK query
        """
        pass

    @abstractmethod
    def load_rdf(
        self,
        data: str,
        format: str = "turtle",
        graph_uri: str | None = None,
    ) -> bool:
        """
        Load RDF data into the store.
        
        Args:
            data: RDF data as string
            format: RDF format ("turtle", "json-ld", "xml", etc.)
            graph_uri: Optional named graph URI
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate that the store configuration is valid.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Store name identifier (e.g., 'fuseki', 'blazegraph', 'stardog').
        
        Returns:
            Store name string
        """
        pass

    @property
    @abstractmethod
    def query_endpoint(self) -> str:
        """Get the SPARQL query endpoint URL."""
        pass

    @property
    @abstractmethod
    def update_endpoint(self) -> str:
        """Get the SPARQL update endpoint URL."""
        pass

    @property
    @abstractmethod
    def graph_store_endpoint(self) -> str:
        """Get the Graph Store Protocol endpoint URL."""
        pass
