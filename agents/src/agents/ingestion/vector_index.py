"""
Vector Index Agent - Indexes clause text in Milvus for semantic search.
"""

from typing import Any

from pydantic import BaseModel, Field

import json

from agents.shared.base import BaseAgent
from agents.ingestion.clause_extraction import ExtractedClause
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class IndexResult(BaseModel):
    """Result of vector indexing."""
    
    success: bool = Field(description="Whether indexing was successful")
    indexed_count: int = Field(default=0, description="Number of clauses indexed")
    skipped_count: int = Field(default=0, description="Number of clauses skipped")
    collection_name: str = Field(default="", description="Name of the Milvus collection")
    message: str = Field(default="", description="Status message")
    error: str | None = Field(default=None, description="Error message if failed")


class VectorIndexAgent(BaseAgent):
    """
    Agent for indexing contract clauses in Milvus vector store.
    
    Features:
    - Batch embedding generation
    - Metadata association (clause type, contract ID)
    - Duplicate detection
    - Index management
    """

    def __init__(self, vector_store: VectorStore | None = None, **kwargs: Any):
        """
        Initialize the vector index agent.
        
        Args:
            vector_store: Optional pre-configured VectorStore (injected via dependency injection)
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.settings = get_settings()
        # Use dependency injection - get from service factory if not provided
        if vector_store is None:
            service_factory = get_service_factory(settings=self.settings)
            vector_store = service_factory.get_vector_store()
        self._vector_store = vector_store

    @property
    def vector_store(self) -> VectorStore:
        """Get vector store instance."""
        return self._vector_store

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> IndexResult:
        """
        Index clauses in Milvus with RDF linking.
        
        Args:
            input_data: Dict with:
                - 'clauses': List of ExtractedClause or dicts
                - 'contract_id': ID of the parent contract
                - 'document_id': Document identifier for graph URI
                - 'rdf_uris': Optional dict mapping clause_id to RDF URI
                
        Returns:
            IndexResult with status
        """
        clauses = input_data.get("clauses", [])
        contract_id = input_data.get("contract_id", "unknown")
        document_id = input_data.get("document_id", contract_id)
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        rdf_uris = input_data.get("rdf_uris", {})
        
        self.log_start(
            "vector_indexing",
            contract_id=contract_id,
            clause_count=len(clauses)
        )
        
        if not clauses:
            return IndexResult(
                success=True,
                indexed_count=0,
                message="No clauses to index",
                collection_name=self.settings.milvus_collection,
            )
        
        try:
            # Import graph manager for URI generation
            from graph_manager import get_graph_manager
            graph_manager = get_graph_manager()
            graph_uri = graph_manager.get_document_graph_uri(document_id)
            
            # Convert to indexable format
            indexable_clauses = []
            skipped = 0
            
            for clause in clauses:
                # Handle both ExtractedClause and dict
                if isinstance(clause, ExtractedClause):
                    clause_id = clause.clause_id
                    clause_type = clause.clause_type
                    text = clause.raw_text
                    summary = clause.summary
                    key_points = getattr(clause, "key_points", []) or []
                    structured_summary = getattr(clause, "structured_summary", {}) or {}
                else:
                    clause_id = clause.get("clause_id", "")
                    clause_type = clause.get("clause_type", "")
                    text = clause.get("raw_text", clause.get("text", ""))
                    summary = clause.get("summary", "")
                    key_points = clause.get("key_points", []) or []
                    structured_summary = clause.get("structured_summary", {}) or {}
                
                # Skip empty text
                if not text or len(text.strip()) < 10:
                    skipped += 1
                    continue
                
                # Get or generate RDF URI
                rdf_uri = rdf_uris.get(clause_id, "")
                if not rdf_uri:
                    # Generate default RDF URI
                    rdf_uri = (
                        f"{self.settings.contract_namespace}"
                        f"{clause_id}"
                    )
                
                # Extract DocTags metadata from clause (populated by Docling pipeline)
                if isinstance(clause, ExtractedClause):
                    sec_title = getattr(clause, "section_title", "") or ""
                    has_table_val = "true" if getattr(clause, "has_table", False) else "false"
                    page_range = getattr(clause, "page_range", "") or ""
                    source_section = getattr(clause, "source_section_id", "") or ""
                else:
                    sec_title = clause.get("section_title", "")
                    has_table_val = "true" if clause.get("has_table", False) else "false"
                    page_range = clause.get("page_range", "")
                    source_section = clause.get("source_section_id", "")

                source_pipeline = (
                    "docling"
                    if sec_title or source_section
                    else input_data.get("source_pipeline", "legacy")
                )

                indexable_clauses.append({
                    "clause_id": clause_id,
                    "contract_id": contract_id,
                    "clause_type": clause_type,
                    "text": text,
                    "summary": summary,
                    "key_points": json.dumps(key_points),
                    "structured_summary": json.dumps(structured_summary),
                    "rdf_uri": rdf_uri,
                    "graph_uri": graph_uri,
                    "section_title": sec_title,
                    "has_table": has_table_val,
                    "page_range": page_range,
                    "source_pipeline": source_pipeline,
                })
            
            # Batch index
            if indexable_clauses:
                indexed = self.vector_store.add_clauses_batch(indexable_clauses)
            else:
                indexed = 0
            
            result = IndexResult(
                success=True,
                indexed_count=indexed,
                skipped_count=skipped,
                collection_name=self.settings.milvus_collection,
                message=f"Indexed {indexed} clauses, skipped {skipped}",
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("collection_name", self.settings.milvus_collection)
                self._save_explanation()
            
            self.log_complete(
                "vector_indexing",
                indexed_count=indexed,
                skipped_count=skipped,
            )
            
            return result
            
        except Exception as e:
            logger.exception("vector_indexing failed: %s", e)
            self.log_error("vector_indexing", e, contract_id=contract_id)
            return IndexResult(
                success=False,
                error=str(e),
                collection_name=self.settings.milvus_collection,
            )

    async def index_single_clause(
        self,
        clause_id: str,
        text: str,
        contract_id: str = "",
        clause_type: str = "",
        rdf_uri: str = "",
        graph_uri: str = "",
    ) -> bool:
        """Index a single clause with RDF linking."""
        try:
            self.vector_store.add_clause(
                clause_id=clause_id,
                text=text,
                contract_id=contract_id,
                clause_type=clause_type,
                rdf_uri=rdf_uri,
                graph_uri=graph_uri,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to index clause: {e}")
            return False

    async def search_similar(
        self,
        query: str,
        top_k: int = 5,
        clause_type: str | None = None,
        contract_id: str | None = None,
        graph_uri: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for similar clauses with graph filtering.
        
        Args:
            query: Search query text
            top_k: Number of results
            clause_type: Optional filter by type
            contract_id: Optional filter by contract
            graph_uri: Optional filter by named graph
            
        Returns:
            List of matching clauses with scores and RDF URIs
        """
        return self.vector_store.search(
            query=query,
            top_k=top_k,
            clause_type=clause_type,
            contract_id=contract_id,
            graph_uri=graph_uri,
        )

    async def delete_contract_clauses(self, contract_id: str) -> int:
        """Delete all clauses for a contract from the index."""
        return self.vector_store.delete_by_contract(contract_id)

    async def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the vector index."""
        return self.vector_store.get_collection_stats()

    async def reindex_from_fuseki(self, fuseki_client: Any) -> IndexResult:
        """
        Reindex all clauses from Fuseki.
        
        Args:
            fuseki_client: FusekiClient instance
            
        Returns:
            IndexResult with status
        """
        self.log_start("reindex_from_fuseki")
        
        # Query all clauses from Fuseki
        query = """
            PREFIX proc: <http://procurement.kg/ontology#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?clause ?clauseType ?contract ?text WHERE {
                ?contract proc:hasClause ?clause .
                ?clause a ?clauseType .
                ?clause proc:rawText ?text .
                FILTER(CONTAINS(STR(?clauseType), "Clause"))
            }
        """
        
        try:
            results = fuseki_client.execute_select(query)
            
            clauses = []
            for row in results:
                clause_uri = row.get("clause", "")
                clause_id = clause_uri.split("#")[-1] if "#" in clause_uri else clause_uri.split("/")[-1]
                
                clause_type_uri = row.get("clauseType", "")
                clause_type = clause_type_uri.split("#")[-1] if "#" in clause_type_uri else clause_type_uri.split("/")[-1]
                
                contract_uri = row.get("contract", "")
                contract_id = contract_uri.split("#")[-1] if "#" in contract_uri else contract_uri.split("/")[-1]
                
                clauses.append({
                    "clause_id": clause_id,
                    "contract_id": contract_id,
                    "clause_type": clause_type,
                    "text": row.get("text", ""),
                })
            
            # Index all clauses
            result = await self.process({
                "clauses": [
                    {"clause_id": c["clause_id"], "clause_type": c["clause_type"], "text": c["text"]}
                    for c in clauses
                ],
                "contract_id": "reindex",
            })
            
            # Update with actual contract IDs
            for clause in clauses:
                # Update metadata would require delete/re-add in Milvus
                pass
            
            self.log_complete("reindex_from_fuseki", count=len(clauses))
            
            return result
            
        except Exception as e:
            self.log_error("reindex_from_fuseki", e)
            return IndexResult(
                success=False,
                error=str(e),
            )
