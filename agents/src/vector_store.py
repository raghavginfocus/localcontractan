"""
Milvus Vector Store client for semantic search over contract clauses.
"""

from typing import Any

from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from sentence_transformers import SentenceTransformer

from config import Settings, get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class MilvusVectorStore:
    """
    Milvus-based vector store for contract clause embeddings.
    
    Features:
    - Semantic search over clause text
    - Metadata filtering (clause type, contract, etc.)
    - Batch insertion for efficiency
    - Automatic schema creation
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize the Milvus vector store."""
        self.settings = settings or get_settings()
        self.collection_name = self.settings.milvus_collection
        self.embedding_dim = self.settings.embedding_dim
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(self.settings.embedding_model)
        
        # Connect to Milvus
        self._connect()
        
        # Ensure collection exists
        self._ensure_collection()
        
        logger.info(
            "MilvusVectorStore initialized",
            host=self.settings.milvus_host,
            port=self.settings.milvus_port,
            collection=self.collection_name,
        )

    def _connect(self) -> None:
        """Connect to Milvus server."""
        connections.connect(
            alias="default",
            host=self.settings.milvus_host,
            port=self.settings.milvus_port,
        )
        logger.debug("Connected to Milvus")

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            self.collection.load()
            logger.debug("Loaded existing collection", collection=self.collection_name)
            return
        
        # Define schema with RDF URI linking
        fields = [
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=128,
            ),
            FieldSchema(
                name="clause_id",
                dtype=DataType.VARCHAR,
                max_length=128,
            ),
            FieldSchema(
                name="contract_id",
                dtype=DataType.VARCHAR,
                max_length=128,
            ),
            FieldSchema(
                name="clause_type",
                dtype=DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                name="text",
                dtype=DataType.VARCHAR,
                max_length=65535,
            ),
            FieldSchema(
                name="rdf_uri",
                dtype=DataType.VARCHAR,
                max_length=512,
                description="RDF URI linking to knowledge graph",
            ),
            FieldSchema(
                name="graph_uri",
                dtype=DataType.VARCHAR,
                max_length=512,
                description="Named graph URI for isolation",
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.embedding_dim,
            ),
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description="Contract clause embeddings for semantic search",
        )
        
        # Create collection
        self.collection = Collection(
            name=self.collection_name,
            schema=schema,
        )
        
        # Create index on embedding field for fast similarity search
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        self.collection.create_index(
            field_name="embedding",
            index_params=index_params,
        )
        
        # Load collection into memory
        self.collection.load()
        
        logger.info("Created new Milvus collection", collection=self.collection_name)

    def add_clause(
        self,
        clause_id: str,
        text: str,
        contract_id: str = "",
        clause_type: str = "",
        rdf_uri: str = "",
        graph_uri: str = "",
    ) -> None:
        """
        Add a single clause to the vector store with RDF linking.
        
        Args:
            clause_id: Unique identifier for the clause
            text: Clause text content
            contract_id: Parent contract ID
            clause_type: Type of clause (e.g., TerminationClause)
            rdf_uri: RDF URI of the clause in the knowledge graph
            graph_uri: Named graph URI for isolation
        """
        embedding = self.embedding_model.encode(text).tolist()
        
        data = [
            [f"{clause_id}_{hash(text) % 10000}"],  # id
            [clause_id],
            [contract_id],
            [clause_type],
            [text[:65000]],  # Truncate if too long
            [rdf_uri],
            [graph_uri],
            [embedding],
        ]
        
        self.collection.insert(data)
        self.collection.flush()
        
        logger.debug(
            "Added clause to vector store",
            clause_id=clause_id,
            rdf_uri=rdf_uri
        )

    def add_clauses_batch(
        self,
        clauses: list[dict[str, Any]],
    ) -> int:
        """
        Add multiple clauses to the vector store in batch with RDF linking.
        
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
        if not clauses:
            return 0
        
        # Prepare data
        ids = []
        clause_ids = []
        contract_ids = []
        clause_types = []
        texts = []
        rdf_uris = []
        graph_uris = []
        embeddings = []
        
        # Batch encode all texts
        all_texts = [c["text"] for c in clauses]
        all_embeddings = self.embedding_model.encode(all_texts)
        
        for i, clause in enumerate(clauses):
            clause_id = clause["clause_id"]
            text = clause["text"]
            
            ids.append(f"{clause_id}_{hash(text) % 10000}")
            clause_ids.append(clause_id)
            contract_ids.append(clause.get("contract_id", ""))
            clause_types.append(clause.get("clause_type", ""))
            texts.append(text[:65000])
            rdf_uris.append(clause.get("rdf_uri", ""))
            graph_uris.append(clause.get("graph_uri", ""))
            embeddings.append(all_embeddings[i].tolist())
        
        data = [
            ids, clause_ids, contract_ids, clause_types,
            texts, rdf_uris, graph_uris, embeddings
        ]
        
        self.collection.insert(data)
        self.collection.flush()
        
        logger.info("Batch inserted clauses", count=len(clauses))
        return len(clauses)

    def search(
        self,
        query: str,
        top_k: int = 5,
        clause_type: str | None = None,
        contract_id: str | None = None,
        graph_uri: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar clauses with RDF linking.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            clause_type: Optional filter by clause type
            contract_id: Optional filter by contract
            graph_uri: Optional filter by named graph
            
        Returns:
            List of matching clauses with scores and RDF URIs
        """
        # Encode query
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Build filter expression
        filter_expr = None
        filters = []
        if clause_type:
            filters.append(f'clause_type == "{clause_type}"')
        if contract_id:
            filters.append(f'contract_id == "{contract_id}"')
        if graph_uri:
            filters.append(f'graph_uri == "{graph_uri}"')
        if filters:
            filter_expr = " && ".join(filters)
        
        # Search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10},
        }
        
        # Execute search
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=[
                "clause_id", "contract_id", "clause_type",
                "text", "rdf_uri", "graph_uri"
            ],
        )
        
        # Format results
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "clause_id": hit.entity.get("clause_id"),
                    "contract_id": hit.entity.get("contract_id"),
                    "clause_type": hit.entity.get("clause_type"),
                    "text": hit.entity.get("text"),
                    "rdf_uri": hit.entity.get("rdf_uri"),
                    "graph_uri": hit.entity.get("graph_uri"),
                    "score": hit.score,
                })
        
        logger.debug(
            "Vector search completed",
            query=query[:50],
            results=len(formatted_results)
        )
        return formatted_results

    def search_by_embedding(
        self,
        embedding: list[float],
        top_k: int = 5,
        graph_uri: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search using a pre-computed embedding with RDF linking."""
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10},
        }
        
        filter_expr = f'graph_uri == "{graph_uri}"' if graph_uri else None
        
        results = self.collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=[
                "clause_id", "contract_id", "clause_type",
                "text", "rdf_uri", "graph_uri"
            ],
        )
        
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "clause_id": hit.entity.get("clause_id"),
                    "contract_id": hit.entity.get("contract_id"),
                    "clause_type": hit.entity.get("clause_type"),
                    "text": hit.entity.get("text"),
                    "rdf_uri": hit.entity.get("rdf_uri"),
                    "graph_uri": hit.entity.get("graph_uri"),
                    "score": hit.score,
                })
        
        return formatted_results

    def delete_by_contract(self, contract_id: str) -> int:
        """Delete all clauses for a contract."""
        expr = f'contract_id == "{contract_id}"'
        result = self.collection.delete(expr)
        self.collection.flush()
        logger.info("Deleted clauses for contract", contract_id=contract_id)
        return result.delete_count if hasattr(result, 'delete_count') else 0

    def delete_by_clause(self, clause_id: str) -> int:
        """Delete a specific clause."""
        expr = f'clause_id == "{clause_id}"'
        result = self.collection.delete(expr)
        self.collection.flush()
        return result.delete_count if hasattr(result, 'delete_count') else 0

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection."""
        self.collection.flush()
        return {
            "name": self.collection_name,
            "num_entities": self.collection.num_entities,
            "schema": str(self.collection.schema),
        }

    def drop_collection(self) -> None:
        """Drop the entire collection (use with caution!)."""
        utility.drop_collection(self.collection_name)
        logger.warning("Dropped collection", collection=self.collection_name)

    def close(self) -> None:
        """Close the connection to Milvus."""
        connections.disconnect("default")
        logger.debug("Disconnected from Milvus")
