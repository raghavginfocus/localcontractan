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
        """Create collection if it doesn't exist with full metadata support."""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            self.collection.load()
            logger.debug("Loaded existing collection", collection=self.collection_name)
            return

        # Define schema with RDF URI linking + summary bundle + CONTRACT METADATA + single embedding
        # (embedding computed from summary + key_points + structured_summary)
        fields = [
            # Primary key
            FieldSchema(
                name="id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=128,
            ),
            # Clause identifiers
            FieldSchema(
                name="clause_id",
                dtype=DataType.VARCHAR,
                max_length=128,
            ),
            FieldSchema(
                name="clause_type",
                dtype=DataType.VARCHAR,
                max_length=64,
            ),
            # Clause content
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
            # RDF linking
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
            
            # ===== CONTRACT METADATA FROM CACHEVIEW.JSON =====
            FieldSchema(
                name="contract_id",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Business Contract ID from cacheview.json",
            ),
            FieldSchema(
                name="doc_id",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Document ID from cacheview.json",
            ),
            FieldSchema(
                name="project_name",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Project name",
            ),
            FieldSchema(
                name="parent_contract",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Parent contract ID",
            ),
            FieldSchema(
                name="doc_name",
                dtype=DataType.VARCHAR,
                max_length=500,
                description="Original document filename",
            ),
            FieldSchema(
                name="doc_type",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="Document type",
            ),
            FieldSchema(
                name="status",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="Contract status",
            ),
            FieldSchema(
                name="supplier_name",
                dtype=DataType.VARCHAR,
                max_length=500,
                description="Supplier/vendor name",
            ),
            FieldSchema(
                name="supplier_id",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Supplier ID",
            ),
            FieldSchema(
                name="owner_name",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Contract owner name",
            ),
            FieldSchema(
                name="owner_id",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Contract owner ID/email",
            ),
            FieldSchema(
                name="effective_date",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="Contract effective date",
            ),
            FieldSchema(
                name="expiration_date",
                dtype=DataType.VARCHAR,
                max_length=100,
                description="Contract expiration date",
            ),
            FieldSchema(
                name="agreement_type",
                dtype=DataType.VARCHAR,
                max_length=500,
                description="Type of agreement",
            ),
            FieldSchema(
                name="business_unit",
                dtype=DataType.VARCHAR,
                max_length=200,
                description="Business unit",
            ),
            
            # DocTags metadata (from Docling pipeline)
            FieldSchema(
                name="section_title",
                dtype=DataType.VARCHAR,
                max_length=512,
                description="DocTags section heading (empty for legacy pipeline)",
            ),
            FieldSchema(
                name="has_table",
                dtype=DataType.VARCHAR,
                max_length=8,
                description="'true'/'false' — clause contains a table (from DocTags)",
            ),
            FieldSchema(
                name="page_range",
                dtype=DataType.VARCHAR,
                max_length=32,
                description="Source page range e.g. '5-6' (from DocTags provenance)",
            ),
            FieldSchema(
                name="source_pipeline",
                dtype=DataType.VARCHAR,
                max_length=32,
                description="'docling' or 'legacy' — which ingestion pipeline produced this",
            ),
            # Vector embedding
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=self.embedding_dim,
                description="Embedding computed from summary + key metadata (for fast semantic search)",
            ),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Contract clauses with full metadata from cacheview.json for semantic search",
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
        
        # Create scalar indexes for metadata fields (for fast filtering)
        scalar_index_fields = [
            "contract_id",      # Business Contract ID
            "clause_type",      # Clause type filtering
            "supplier_name",    # Supplier filtering
            "owner_id",         # Owner filtering
            "agreement_type",   # Agreement type filtering
        ]
        
        for field_name in scalar_index_fields:
            try:
                self.collection.create_index(
                    field_name=field_name,
                    index_params={"index_type": "INVERTED"}
                )
                logger.debug(f"Created scalar index on {field_name}")
            except Exception as e:
                logger.warning(
                    f"Could not create index on {field_name}: {e}",
                    field=field_name,
                    error=str(e)
                )

        # Load collection into memory
        self.collection.load()

        logger.info(
            "Created new Milvus collection with metadata support",
            collection=self.collection_name,
            total_fields=len(fields),
            metadata_fields=15,  # Number of contract metadata fields
        )

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
        desired_fields = [
            "clause_id", "contract_id", "clause_type",
            "text", "summary", "key_points", "structured_summary",
            "rdf_uri", "graph_uri",
            "section_title", "has_table", "page_range", "source_pipeline",
        ]
        existing_fields = {f.name for f in self.collection.schema.fields}
        output_fields = [f for f in desired_fields if f in existing_fields]

        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=output_fields,
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
                    "section_title": hit.entity.get("section_title", ""),
                    "has_table": hit.entity.get("has_table", ""),
                    "page_range": hit.entity.get("page_range", ""),
                    "source_pipeline": hit.entity.get("source_pipeline", ""),
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

        # Prepare data for ALL fields (basic + metadata)
        ids = []
        clause_ids = []
        clause_types = []
        texts = []
        summaries = []
        key_points_list = []
        structured_summaries = []
        rdf_uris = []
        graph_uris = []
        
        # Contract metadata fields (from cacheview.json)
        contract_ids = []
        doc_ids = []
        project_names = []
        parent_contracts = []
        doc_names = []
        doc_types = []
        statuses = []
        supplier_names = []
        supplier_ids = []
        owner_names = []
        owner_ids = []
        effective_dates = []
        expiration_dates = []
        agreement_types = []
        business_units = []
        
        # DocTags metadata
        section_titles = []
        has_tables = []
        page_ranges = []
        source_pipelines = []
        
        embeddings = []

        # Build embedding text: summary + key metadata (optimized for semantic search)
        embedding_texts = []
        for clause in clauses:
            summary = clause.get("summary", "") or ""
            clause_type = clause.get("clause_type", "")
            key_points_str = clause.get("key_points", "")
            structured_str = clause.get("structured_summary", "")
            sec_title = clause.get("section_title", "")
            
            embedding_parts = [f"[{clause_type}]"]
            # Include section title for better semantic context
            if sec_title:
                embedding_parts.append(f"Section: {sec_title}")
            if summary:
                embedding_parts.append(f"Summary: {summary}")
            if key_points_str:
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

            # Basic fields
            ids.append(f"{clause_id}_{hash(text) % 10000}")
            clause_ids.append(clause_id)
            clause_types.append(clause.get("clause_type", ""))
            texts.append(text[:65000])
            summaries.append((clause.get("summary") or "")[:4095])
            key_points_list.append((clause.get("key_points") or "")[:8191])
            structured_summaries.append((clause.get("structured_summary") or "")[:16383])
            rdf_uris.append(clause.get("rdf_uri", ""))
            graph_uris.append(clause.get("graph_uri", ""))
            
            # Contract metadata fields (from cacheview.json)
            contract_ids.append((clause.get("contract_id") or "")[:199])
            doc_ids.append((clause.get("doc_id") or "")[:199])
            project_names.append((clause.get("project_name") or "")[:199])
            parent_contracts.append((clause.get("parent_contract") or "")[:199])
            doc_names.append((clause.get("doc_name") or "")[:499])
            doc_types.append((clause.get("doc_type") or "")[:99])
            statuses.append((clause.get("status") or "")[:99])
            supplier_names.append((clause.get("supplier_name") or "")[:499])
            supplier_ids.append((clause.get("supplier_id") or "")[:199])
            owner_names.append((clause.get("owner_name") or "")[:199])
            owner_ids.append((clause.get("owner_id") or "")[:199])
            effective_dates.append((clause.get("effective_date") or "")[:99])
            expiration_dates.append((clause.get("expiration_date") or "")[:99])
            agreement_types.append((clause.get("agreement_type") or "")[:499])
            business_units.append((clause.get("business_unit") or "")[:199])
            
            # DocTags metadata
            section_titles.append((clause.get("section_title") or "")[:511])
            has_tables.append(clause.get("has_table", "false"))
            page_ranges.append((clause.get("page_range") or "")[:31])
            source_pipelines.append((clause.get("source_pipeline") or "legacy")[:15])
            
            embeddings.append(all_embeddings[i].tolist())

        # Data array MUST match the order of fields in schema definition
        data = [
            ids,                    # 1. id (primary key)
            clause_ids,             # 2. clause_id
            clause_types,           # 3. clause_type
            texts,                  # 4. text
            summaries,              # 5. summary
            key_points_list,        # 6. key_points
            structured_summaries,   # 7. structured_summary
            rdf_uris,               # 8. rdf_uri
            graph_uris,             # 9. graph_uri
            # Contract metadata (15 fields)
            contract_ids,           # 10. contract_id
            doc_ids,                # 11. doc_id
            project_names,          # 12. project_name
            parent_contracts,       # 13. parent_contract
            doc_names,              # 14. doc_name
            doc_types,              # 15. doc_type
            statuses,               # 16. status
            supplier_names,         # 17. supplier_name
            supplier_ids,           # 18. supplier_id
            owner_names,            # 19. owner_name
            owner_ids,              # 20. owner_id
            effective_dates,        # 21. effective_date
            expiration_dates,       # 22. expiration_date
            agreement_types,        # 23. agreement_type
            business_units,         # 24. business_unit
            # DocTags metadata (4 fields)
            section_titles,         # 25. section_title
            has_tables,             # 26. has_table
            page_ranges,            # 27. page_range
            source_pipelines,       # 28. source_pipeline
            embeddings,             # 29. embedding
        ]

        self.collection.insert(data)
        self.collection.flush()

        logger.info(
            "Batch inserted clauses with full metadata",
            count=len(clauses),
            fields=len(data),
            sample_contract_id=contract_ids[0] if contract_ids else "N/A",
            sample_supplier=supplier_names[0] if supplier_names else "N/A",
        )
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
