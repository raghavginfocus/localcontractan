"""
Milvus Vector Store Implementation

Concrete implementation of VectorStore for Milvus.
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
from storage.vector.base import VectorStore
from logger import get_module_logger

logger = get_module_logger(__name__)


class MilvusStore(VectorStore):
    """
    Vector Store implementation for Milvus.
    
    This is a wrapper around the existing MilvusVectorStore functionality,
    implementing the VectorStore interface for abstraction.
    """

    def __init__(self, settings: Settings | None = None, lazy_load: bool = True):
        """
        Initialize the Milvus store with optional lazy loading.
        
        Args:
            settings: Configuration settings
            lazy_load: If True, delay embedding model loading until first use
        """
        self.settings = settings or get_settings()
        # Use a versioned collection for new schema (summary-based embeddings + summaries)
        # to avoid schema incompatibilities with existing collections.
        # Note: Milvus supports only one vector field per collection, so we use
        # a single embedding computed from summary + key metadata for optimal search.
        self.collection_name = getattr(self.settings, "milvus_collection_v2", None)
        if not self.collection_name:
            self.collection_name = f"{self.settings.milvus_collection}_v2"
        self.embedding_dim = self.settings.embedding_dim

        # Lazy load embedding model for faster startup
        self._embedding_model = None
        self._lazy_load = lazy_load
        if not lazy_load:
            self._embedding_model = SentenceTransformer(self.settings.embedding_model)
        
        # Simple in-memory cache for query embeddings to avoid recomputing
        # embeddings for repeated questions (common in testing/evaluation).
        self._query_embedding_cache: dict[str, list[float]] = {}

        # Connect to Milvus with connection pooling
        self._connect()

        # Ensure collection exists
        self._ensure_collection()

        logger.info(
            "MilvusStore initialized",
            host=self.settings.milvus_host,
            port=self.settings.milvus_port,
            collection=self.collection_name,
            lazy_load=lazy_load,
        )

    @property
    def embedding_model(self) -> SentenceTransformer:
        """Lazy load embedding model on first access."""
        if self._embedding_model is None:
            logger.debug("Loading embedding model (lazy initialization)")
            self._embedding_model = SentenceTransformer(self.settings.embedding_model)
        return self._embedding_model

    @property
    def name(self) -> str:
        return "milvus"

    def validate_config(self) -> bool:
        """Validate Milvus configuration."""
        return bool(self.settings.milvus_host and self.settings.milvus_port)

    def _connect(self) -> None:
        """Connect to Milvus server with connection pooling."""
        # Check if already connected
        try:
            if connections.has_connection("default"):
                logger.debug("Reusing existing Milvus connection")
                return
        except Exception:
            pass
        
        # Create new connection with retries (Milvus can take time to become ready)
        import time
        last_err: Exception | None = None
        for attempt in range(1, 16):  # ~1-2 minutes total with backoff
            try:
                connections.connect(
                    alias="default",
                    host=self.settings.milvus_host,
                    port=self.settings.milvus_port,
                    pool_size=10,  # Connection pool size
                )
                logger.debug(
                    "Connected to Milvus with connection pooling",
                    attempt=attempt,
                )
                return
            except Exception as e:
                last_err = e
                sleep_s = min(8.0, 0.5 * (2 ** (attempt - 1)))
                logger.warning(
                    "Milvus not ready yet, retrying connect",
                    attempt=attempt,
                    sleep_seconds=sleep_s,
                    error=str(e),
                )
                time.sleep(sleep_s)
        
        raise last_err if last_err else RuntimeError("Failed to connect to Milvus")

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            self.collection.load()
            logger.debug("Loaded existing collection", collection=self.collection_name)
            return

        # Define schema with RDF URI linking + summary bundle + single embedding
        # (embedding computed from summary + key_points + structured_summary)
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
                name="summary",
                dtype=DataType.VARCHAR,
                max_length=4096,
                description="Short summary (1-2 sentences)",
            ),
            FieldSchema(
                name="key_points",
                dtype=DataType.VARCHAR,
                max_length=8192,
                description="Key points (bullet list) serialized as text/JSON",
            ),
            FieldSchema(
                name="structured_summary",
                dtype=DataType.VARCHAR,
                max_length=16384,
                description="Structured summary serialized as JSON",
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
                description="Embedding computed from summary + key metadata (for fast semantic search)",
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

        # Create index on embedding field
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

    def search(
        self,
        query: str,
        top_k: int = 5,
        clause_type: str | None = None,
        contract_id: str | None = None,
        graph_uri: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar clauses using summary-based embeddings.
        
        The embedding is computed from: summary + key_points + structured_summary,
        providing rich semantic signal while keeping the index fast.
        """
        # Encode query (with small cache)
        cache_key = query.strip().lower()
        query_embedding = self._query_embedding_cache.get(cache_key)
        if query_embedding is None:
            query_embedding = self.embedding_model.encode(query).tolist()
            # Keep cache bounded
            if len(self._query_embedding_cache) < 256:
                self._query_embedding_cache[cache_key] = query_embedding

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

        # Optimized search parameters for approximate nearest neighbor
        # Lower nprobe for faster search with acceptable accuracy trade-off
        search_params = {
            "metric_type": "COSINE",
            "params": {
                "nprobe": 5,  # Reduced from 10 for 2x faster search
                "ef": 64,  # For HNSW index if used
            },
        }

        # Execute search on summary-based embedding
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=[
                "clause_id", "contract_id", "clause_type",
                "text", "summary", "key_points", "structured_summary",
                "rdf_uri", "graph_uri",
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
                    "summary": hit.entity.get("summary"),
                    "key_points": hit.entity.get("key_points"),
                    "structured_summary": hit.entity.get("structured_summary"),
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

    def add_clauses_batch(
        self,
        clauses: list[dict[str, Any]],
    ) -> int:
        """Add multiple clauses to the vector store in batch."""
        if not clauses:
            return 0

        # Prepare data
        ids = []
        clause_ids = []
        contract_ids = []
        clause_types = []
        texts = []
        summaries = []
        key_points_list = []
        structured_summaries = []
        rdf_uris = []
        graph_uris = []
        embeddings = []

        # Build embedding text: summary + key metadata (optimized for semantic search)
        embedding_texts = []
        for clause in clauses:
            summary = clause.get("summary", "") or ""
            clause_type = clause.get("clause_type", "")
            key_points_str = clause.get("key_points", "")
            structured_str = clause.get("structured_summary", "")
            
            # Build rich embedding text from summary + metadata
            embedding_parts = [f"[{clause_type}]"]
            if summary:
                embedding_parts.append(f"Summary: {summary}")
            if key_points_str:
                # Parse key points if JSON, otherwise use as-is
                try:
                    import json
                    kp_list = json.loads(key_points_str) if key_points_str.startswith("[") else [key_points_str]
                    embedding_parts.append(f"Key points: {'; '.join(kp_list[:5])}")
                except Exception:
                    embedding_parts.append(f"Key points: {key_points_str[:200]}")
            if structured_str:
                try:
                    import json
                    struct = json.loads(structured_str) if structured_str.startswith("{") else {}
                    # Add key structured fields to embedding
                    for key in ["notice_period_days", "payment_terms_days", "risk_level"]:
                        if key in struct and struct[key]:
                            embedding_parts.append(f"{key}: {struct[key]}")
                except Exception:
                    pass
            
            embedding_text = " ".join(embedding_parts)
            embedding_texts.append(embedding_text if embedding_text else clause.get("text", "")[:500])

        # Batch encode embedding texts (summary + metadata)
        all_embeddings = self.embedding_model.encode(embedding_texts)

        for i, clause in enumerate(clauses):
            clause_id = clause["clause_id"]
            text = clause["text"]

            ids.append(f"{clause_id}_{hash(text) % 10000}")
            clause_ids.append(clause_id)
            contract_ids.append(clause.get("contract_id", ""))
            clause_types.append(clause.get("clause_type", ""))
            texts.append(text[:65000])
            summaries.append((clause.get("summary") or "")[:4095])
            key_points_list.append((clause.get("key_points") or "")[:8191])
            structured_summaries.append((clause.get("structured_summary") or "")[:16383])
            rdf_uris.append(clause.get("rdf_uri", ""))
            graph_uris.append(clause.get("graph_uri", ""))
            embeddings.append(all_embeddings[i].tolist())

        data = [
            ids, clause_ids, contract_ids, clause_types,
            texts, summaries, key_points_list, structured_summaries,
            rdf_uris, graph_uris, embeddings
        ]

        self.collection.insert(data)
        self.collection.flush()

        logger.info("Batch inserted clauses", count=len(clauses))
        return len(clauses)

    def delete_by_contract(self, contract_id: str) -> int:
        """Delete all clauses for a contract."""
        expr = f'contract_id == "{contract_id}"'
        result = self.collection.delete(expr)
        self.collection.flush()
        logger.info("Deleted clauses for contract", contract_id=contract_id)
        return result.delete_count if hasattr(result, 'delete_count') else 0

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection."""
        self.collection.flush()
        return {
            "name": self.collection_name,
            "num_entities": self.collection.num_entities,
            "schema": str(self.collection.schema),
        }
