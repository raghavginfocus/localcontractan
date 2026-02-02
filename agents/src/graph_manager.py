"""
Graph Manager - Manages named graphs for multi-tenancy and isolation.

Provides:
- Per-document graph isolation
- Per-tenant graph organization
- Graph lifecycle management
- Query rewriting for graph-scoped operations
"""

from typing import Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from rdflib import Graph, Namespace, URIRef

from storage.sparql.base import SPARQLStore
from service_factory import get_service_factory
from config import Settings, get_settings
from logger import get_module_logger


class GraphType(str, Enum):
    """Types of named graphs in the system."""
    ONTOLOGY = "ontology"
    DOCUMENT = "document"
    TENANT = "tenant"
    INFERRED = "inferred"
    METADATA = "metadata"


class GraphInfo(BaseModel):
    """Information about a named graph."""
    
    graph_uri: str = Field(description="URI of the named graph")
    graph_type: GraphType = Field(description="Type of graph")
    created_at: datetime = Field(description="Creation timestamp")
    triple_count: int = Field(default=0, description="Number of triples")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class GraphManager:
    """
    Manages named graphs for multi-tenancy and data isolation.
    
    Graph URI Structure:
    - Ontology: http://procurement.kg/graph/ontology
    - Document: http://procurement.kg/graph/doc/{document_id}
    - Tenant: http://procurement.kg/graph/tenant/{tenant_id}
    - Inferred: http://procurement.kg/graph/inferred/{document_id}
    - Metadata: http://procurement.kg/graph/metadata
    
    Features:
    - Isolated document graphs
    - Tenant-level aggregation
    - Separate inferred facts
    - Graph lifecycle management
    - Query rewriting for graph scope
    """
    
    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize GraphManager.
        
        Args:
            sparql_store: Optional SPARQL store instance (injected via dependency injection)
            settings: Application settings
        """
        self.settings = settings or get_settings()
        # Use dependency injection - get from service factory if not provided
        if sparql_store is None:
            service_factory = get_service_factory(settings=self.settings)
            sparql_store = service_factory.get_sparql_store()
        self.sparql_store = sparql_store
        # Backward compatibility (deprecated)
        self.fuseki_client = self.sparql_store
        self.base_graph_uri = "http://procurement.kg/graph"
        self.logger = get_module_logger(__name__).bind(
            component="GraphManager"
        )
    
    def get_ontology_graph_uri(self) -> str:
        """Get URI for the ontology graph."""
        return f"{self.base_graph_uri}/ontology"
    
    def get_document_graph_uri(self, document_id: str) -> str:
        """Get URI for a document's graph."""
        return f"{self.base_graph_uri}/doc/{document_id}"
    
    def get_tenant_graph_uri(self, tenant_id: str) -> str:
        """Get URI for a tenant's aggregated graph."""
        return f"{self.base_graph_uri}/tenant/{tenant_id}"
    
    def get_inferred_graph_uri(self, document_id: str) -> str:
        """Get URI for a document's inferred facts graph."""
        return f"{self.base_graph_uri}/inferred/{document_id}"
    
    def get_metadata_graph_uri(self) -> str:
        """Get URI for the metadata graph."""
        return f"{self.base_graph_uri}/metadata"
    
    def create_document_graph(
        self,
        document_id: str,
        rdf_graph: Graph,
        tenant_id: str | None = None,
    ) -> GraphInfo:
        """
        Create a new document graph.
        
        Args:
            document_id: Unique document identifier
            rdf_graph: RDF graph to load
            tenant_id: Optional tenant identifier
            
        Returns:
            GraphInfo with graph details
        """
        graph_uri = self.get_document_graph_uri(document_id)
        
        self.logger.info(
            "Creating document graph",
            document_id=document_id,
            graph_uri=graph_uri,
            tenant_id=tenant_id,
        )
        
        # Load graph into Fuseki
        self.sparql_store.load_rdf(
            data=rdf_graph.serialize(format="turtle"),
            format="turtle",
            graph_uri=graph_uri,
        )
        
        # Store metadata
        metadata = {
            "document_id": document_id,
            "tenant_id": tenant_id,
        }
        
        self._store_graph_metadata(
            graph_uri=graph_uri,
            graph_type=GraphType.DOCUMENT,
            metadata=metadata,
        )
        
        return GraphInfo(
            graph_uri=graph_uri,
            graph_type=GraphType.DOCUMENT,
            created_at=datetime.now(),
            triple_count=len(rdf_graph),
            metadata=metadata,
        )
    
    def create_inferred_graph(
        self,
        document_id: str,
        inferred_triples: Graph,
    ) -> GraphInfo:
        """
        Create a graph for inferred facts.
        
        Args:
            document_id: Document identifier
            inferred_triples: Graph with inferred triples
            
        Returns:
            GraphInfo
        """
        graph_uri = self.get_inferred_graph_uri(document_id)
        
        self.logger.info(
            "Creating inferred graph",
            document_id=document_id,
            graph_uri=graph_uri,
            triple_count=len(inferred_triples),
        )
        
        self.sparql_store.load_rdf(
            data=inferred_triples.serialize(format="turtle"),
            format="turtle",
            graph_uri=graph_uri,
        )
        
        return GraphInfo(
            graph_uri=graph_uri,
            graph_type=GraphType.INFERRED,
            created_at=datetime.now(),
            triple_count=len(inferred_triples),
            metadata={"document_id": document_id},
        )
    
    def query_document(
        self,
        document_id: str,
        sparql_query: str,
        include_inferred: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Query a specific document's graph.
        
        Args:
            document_id: Document identifier
            sparql_query: SPARQL SELECT query (without GRAPH clause)
            include_inferred: Whether to include inferred facts
            
        Returns:
            Query results
        """
        doc_graph_uri = self.get_document_graph_uri(document_id)
        
        # Rewrite query to use GRAPH clause
        if include_inferred:
            inferred_graph_uri = self.get_inferred_graph_uri(document_id)
            rewritten_query = self._rewrite_query_for_graphs(
                sparql_query,
                [doc_graph_uri, inferred_graph_uri]
            )
        else:
            rewritten_query = self._rewrite_query_for_graphs(
                sparql_query,
                [doc_graph_uri]
            )
        
        return self.sparql_store.execute_select(rewritten_query)
    
    def query_tenant(
        self,
        tenant_id: str,
        sparql_query: str,
        include_inferred: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Query all documents for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            sparql_query: SPARQL SELECT query
            include_inferred: Whether to include inferred facts
            
        Returns:
            Query results across all tenant documents
        """
        # Get all document graphs for tenant
        doc_graphs = self._get_tenant_document_graphs(tenant_id)
        
        if include_inferred:
            # Add inferred graphs
            inferred_graphs = [
                self.get_inferred_graph_uri(doc_id)
                for doc_id in self._extract_document_ids(doc_graphs)
            ]
            all_graphs = doc_graphs + inferred_graphs
        else:
            all_graphs = doc_graphs
        
        # Rewrite query for multiple graphs
        rewritten_query = self._rewrite_query_for_graphs(
            sparql_query,
            all_graphs
        )
        
        return self.sparql_store.execute_select(rewritten_query)
    
    def delete_document_graph(self, document_id: str) -> bool:
        """
        Delete a document's graph and its inferred facts.
        
        Args:
            document_id: Document identifier
            
        Returns:
            True if successful
        """
        doc_graph_uri = self.get_document_graph_uri(document_id)
        inferred_graph_uri = self.get_inferred_graph_uri(document_id)
        
        self.logger.info(
            "Deleting document graphs",
            document_id=document_id,
        )
        
        try:
            # Delete document graph
            self.sparql_store.execute_update(f"DROP SILENT GRAPH <{doc_graph_uri}>")
            
            # Delete inferred graph
            self.sparql_store.execute_update(f"DROP SILENT GRAPH <{inferred_graph_uri}>")
            
            # Remove metadata
            self._delete_graph_metadata(doc_graph_uri)
            self._delete_graph_metadata(inferred_graph_uri)
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to delete document graphs",
                document_id=document_id,
                error=str(e),
            )
            return False
    
    def list_document_graphs(
        self,
        tenant_id: str | None = None
    ) -> list[GraphInfo]:
        """
        List all document graphs, optionally filtered by tenant.
        
        Args:
            tenant_id: Optional tenant filter
            
        Returns:
            List of GraphInfo objects
        """
        # Query metadata graph for document graphs
        if tenant_id:
            query = f"""
            SELECT ?graph ?created ?tenant
            WHERE {{
                GRAPH <{self.get_metadata_graph_uri()}> {{
                    ?graph a <http://procurement.kg/ontology#DocumentGraph> .
                    ?graph <http://procurement.kg/ontology#createdAt> ?created .
                    ?graph <http://procurement.kg/ontology#tenantId> ?tenant .
                    FILTER(?tenant = "{tenant_id}")
                }}
            }}
            """
        else:
            query = f"""
            SELECT ?graph ?created ?tenant
            WHERE {{
                GRAPH <{self.get_metadata_graph_uri()}> {{
                    ?graph a <http://procurement.kg/ontology#DocumentGraph> .
                    ?graph <http://procurement.kg/ontology#createdAt> ?created .
                    OPTIONAL {{ ?graph <http://procurement.kg/ontology#tenantId> ?tenant }}
                }}
            }}
            """
        
        results = self.sparql_store.execute_select(query, add_prefixes=False)
        
        graph_infos = []
        for row in results:
            graph_infos.append(GraphInfo(
                graph_uri=row['graph'],
                graph_type=GraphType.DOCUMENT,
                created_at=datetime.fromisoformat(row['created']),
                metadata={"tenant_id": row.get('tenant')},
            ))
        
        return graph_infos
    
    def get_graph_statistics(self, graph_uri: str) -> dict[str, Any]:
        """
        Get statistics for a specific graph.
        
        Args:
            graph_uri: URI of the graph
            
        Returns:
            Dict with statistics
        """
        count_query = f"""
        SELECT (COUNT(*) as ?count)
        WHERE {{
            GRAPH <{graph_uri}> {{
                ?s ?p ?o .
            }}
        }}
        """
        
        result = self.fuseki_client.execute_select(
            count_query,
            add_prefixes=False
        )
        
        triple_count = int(result[0]['count']) if result else 0
        
        return {
            "graph_uri": graph_uri,
            "triple_count": triple_count,
        }
    
    def _rewrite_query_for_graphs(
        self,
        sparql_query: str,
        graph_uris: list[str]
    ) -> str:
        """
        Rewrite a SPARQL query to use GRAPH clauses.
        
        Converts:
            SELECT ?s ?p ?o WHERE { ?s ?p ?o }
        To:
            SELECT ?s ?p ?o WHERE {
                { GRAPH <uri1> { ?s ?p ?o } }
                UNION
                { GRAPH <uri2> { ?s ?p ?o } }
            }
        """
        # Find WHERE clause
        where_idx = sparql_query.upper().find("WHERE")
        if where_idx == -1:
            return sparql_query
        
        # Extract parts
        select_part = sparql_query[:where_idx + 5]  # Include WHERE
        where_part = sparql_query[where_idx + 5:].strip()
        
        # Remove outer braces if present
        if where_part.startswith("{") and where_part.endswith("}"):
            where_part = where_part[1:-1].strip()
        
        # Build UNION of GRAPH clauses
        graph_clauses = []
        for graph_uri in graph_uris:
            graph_clauses.append(
                f"{{ GRAPH <{graph_uri}> {{ {where_part} }} }}"
            )
        
        union_clause = "\n    UNION\n    ".join(graph_clauses)
        
        return f"{select_part} {{\n    {union_clause}\n}}"
    
    def _store_graph_metadata(
        self,
        graph_uri: str,
        graph_type: GraphType,
        metadata: dict[str, Any],
    ) -> None:
        """Store metadata about a graph."""
        metadata_graph_uri = self.get_metadata_graph_uri()
        
        # Create metadata triples
        g = Graph()
        PROC = Namespace("http://procurement.kg/ontology#")
        
        graph_node = URIRef(graph_uri)
        g.add((graph_node, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
               PROC[f"{graph_type.value.title()}Graph"]))
        g.add((graph_node, PROC.createdAt,
               URIRef(datetime.now().isoformat())))
        
        for key, value in metadata.items():
            if value:
                g.add((graph_node, PROC[key], URIRef(str(value))))
        
        # Load into metadata graph
        self.sparql_store.load_rdf(
            data=g.serialize(format="turtle"),
            format="turtle",
            graph_uri=metadata_graph_uri,
        )
    
    def _delete_graph_metadata(self, graph_uri: str) -> None:
        """Delete metadata for a graph."""
        metadata_graph_uri = self.get_metadata_graph_uri()
        
        delete_query = f"""
        DELETE WHERE {{
            GRAPH <{metadata_graph_uri}> {{
                <{graph_uri}> ?p ?o .
            }}
        }}
        """
        
        self.sparql_store.execute_update(delete_query)
    
    def _get_tenant_document_graphs(self, tenant_id: str) -> list[str]:
        """Get all document graph URIs for a tenant."""
        query = f"""
        SELECT ?graph
        WHERE {{
            GRAPH <{self.get_metadata_graph_uri()}> {{
                ?graph <http://procurement.kg/ontology#tenantId> "{tenant_id}" .
            }}
        }}
        """
        
        results = self.sparql_store.execute_select(query, add_prefixes=False)
        return [row['graph'] for row in results]
    
    def _extract_document_ids(self, graph_uris: list[str]) -> list[str]:
        """Extract document IDs from graph URIs."""
        doc_ids = []
        for uri in graph_uris:
            if "/doc/" in uri:
                doc_id = uri.split("/doc/")[-1]
                doc_ids.append(doc_id)
        return doc_ids


# Global instance
_graph_manager: GraphManager | None = None


def get_graph_manager() -> GraphManager:
    """Get or create the global graph manager instance."""
    global _graph_manager
    if _graph_manager is None:
        _graph_manager = GraphManager()
    return _graph_manager


