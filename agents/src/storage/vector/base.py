"""
Base Vector Store Interface

Abstract base class defining the interface that all vector stores must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class VectorStore(ABC):
    """
    Abstract base class for vector databases.
    
    This abstraction allows swapping between different vector databases
    (Milvus, Pinecone, Weaviate, Qdrant, etc.) without modifying agent code.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        clause_type: str | None = None,
        contract_id: str | None = None,
        graph_uri: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar clauses using semantic similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            clause_type: Optional filter by clause type
            contract_id: Optional filter by contract
            graph_uri: Optional filter by named graph
            
        Returns:
            List of matching clauses with scores and metadata
        """
        pass

    @abstractmethod
    def add_clauses_batch(
        self,
        clauses: list[dict[str, Any]],
    ) -> int:
        """
        Add multiple clauses to the vector store in batch.
        
        Args:
            clauses: List of clause dicts with keys:
                - clause_id: str
                - text: str
                - contract_id: str (optional)
                - clause_type: str (optional)
                - rdf_uri: str (optional) - RDF URI in knowledge graph
                - graph_uri: str (optional) - Named graph URI
                
        Returns:
            Number of clauses inserted
        """
        pass

    @abstractmethod
    def delete_by_contract(self, contract_id: str) -> int:
        """
        Delete all clauses for a contract.
        
        Args:
            contract_id: Contract identifier
            
        Returns:
            Number of clauses deleted
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
        Store name identifier (e.g., 'milvus', 'pinecone', 'weaviate').
        
        Returns:
            Store name string
        """
        pass

    def get_collection_stats(self) -> dict[str, Any]:
        """
        Optional: Get statistics about the collection/store.
        
        Returns:
            Dictionary with statistics (implementation-specific)
        """
        return {}
