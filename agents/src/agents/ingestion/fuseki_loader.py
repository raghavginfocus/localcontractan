"""
Fuseki Loader Agent - Loads validated RDF data into Fuseki triplestore.
"""

from typing import Any

import httpx
from rdflib import Graph, URIRef, Literal
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from storage.sparql.base import SPARQLStore
from service_factory import get_service_factory
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class LoadResult(BaseModel):
    """Result of loading RDF data into Fuseki."""
    
    success: bool = Field(description="Whether the load was successful")
    triple_count: int = Field(default=0, description="Number of triples loaded")
    graph_uri: str | None = Field(default=None, description="Named graph URI if used")
    message: str = Field(default="", description="Status message")
    error: str | None = Field(default=None, description="Error message if failed")


class FusekiLoaderAgent(BaseAgent):
    """
    Agent for loading RDF data into Apache Jena Fuseki.
    
    Supports:
    - Loading Turtle data
    - Loading RDFLib Graph objects
    - Named graph management
    - Batch loading
    - Health checking
    """

    def __init__(self, sparql_store: SPARQLStore | None = None, **kwargs: Any):
        """
        Initialize the Fuseki loader agent.
        
        Args:
            sparql_store: Optional SPARQL store instance (injected via dependency injection)
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(**kwargs)
        self.settings = get_settings()
        # Use dependency injection - get from service factory if not provided
        if sparql_store is None:
            service_factory = get_service_factory(settings=self.settings)
            sparql_store = service_factory.get_sparql_store()
        self.sparql_store = sparql_store
        # Keep endpoints for backward compatibility (deprecated)
        self.data_endpoint = self.sparql_store.graph_store_endpoint
        self.update_endpoint = self.sparql_store.update_endpoint
        self.query_endpoint = self.sparql_store.query_endpoint

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> LoadResult:
        """
        Load RDF data into Fuseki.
        
        Args:
            input_data: Dict with either:
                - 'rdf_data': Turtle string
                - 'graph': RDFLib Graph object
                - 'graph_uri': Optional named graph URI
                
        Returns:
            LoadResult with status
        """
        graph_uri = input_data.get("graph_uri")
        document_id = input_data.get("document_id", graph_uri or "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            input_summary = {
                "has_rdf_data": bool(input_data.get("rdf_data")),
                "has_graph": bool(input_data.get("graph")),
                "graph_uri": graph_uri,
            }
            if input_data.get("rdf_data"):
                input_summary["rdf_data_length"] = len(str(input_data.get("rdf_data")))
            self.explanation_builder.set_input(input_summary)
        
        rdf_data = input_data.get("rdf_data")
        graph = input_data.get("graph")
        graph_uri = input_data.get("graph_uri")
        
        self.log_start("fuseki_load", graph_uri=graph_uri)
        
        # Convert Graph to Turtle if needed
        if graph and not rdf_data:
            rdf_data = graph.serialize(format="turtle")
        
        if not rdf_data:
            return LoadResult(
                success=False,
                error="No RDF data provided",
            )
        
        try:
            result = await self._load_turtle(rdf_data, graph_uri)
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("triple_count", result.triple_count)
                self.explanation_builder.add_metadata("graph_uri", graph_uri)
                self._save_explanation()
            
            self.log_complete(
                "fuseki_load",
                success=result.success,
                triple_count=result.triple_count,
            )
            return result
            
        except Exception as e:
            self.log_error("fuseki_load", e)
            return LoadResult(
                success=False,
                error=str(e),
            )

    async def _load_turtle(self, turtle_data: str, graph_uri: str | None = None) -> LoadResult:
        """
        Load Turtle data using SPARQL store abstraction.
        
        This method uses the SPARQLStore interface, which handles the actual
        loading implementation (Graph Store Protocol or SPARQL UPDATE fallback).
        """
        from rdflib import Graph
        
        # Count triples first
        g = Graph()
        g.parse(data=turtle_data, format="turtle")
        triple_count = len(g)
        
        try:
            # Use SPARQL store abstraction to load RDF
            # Note: load_rdf is synchronous, but we're in an async method
            # For now, we'll call it directly (SPARQLStore could be made async in future)
            success = self.sparql_store.load_rdf(
                data=turtle_data,
                format="turtle",
                graph_uri=graph_uri,
            )
            
            if success:
                return LoadResult(
                    success=True,
                    triple_count=triple_count,
                    graph_uri=graph_uri,
                    message=f"Successfully loaded {triple_count} triples via SPARQL store",
                )
            else:
                return LoadResult(
                    success=False,
                    triple_count=0,
                    graph_uri=graph_uri,
                    error="SPARQL store returned False",
                )
                
        except Exception as e:
            # Fallback to direct HTTP if store abstraction fails
            logger.warning("SPARQL store load failed, trying direct HTTP", error=str(e))
            return await self._load_turtle_direct(turtle_data, graph_uri, triple_count)
    
    async def _load_turtle_direct(
        self, turtle_data: str, graph_uri: str | None = None, triple_count: int = 0
    ) -> LoadResult:
        """Fallback: Load Turtle data via direct HTTP POST."""
        from urllib.parse import quote
        
        # Try Graph Store Protocol first
        url = self.data_endpoint
        
        if graph_uri:
            # URL-encode the graph_uri to handle special characters like #
            encoded_graph_uri = quote(graph_uri, safe='')
            url = f"{url}?graph={encoded_graph_uri}"
        
        headers = {"Content-Type": "text/turtle; charset=utf-8"}
        
        # Only use auth if credentials are provided
        auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            auth = (self.settings.fuseki_user, self.settings.fuseki_password)
        
        async with httpx.AsyncClient(timeout=60.0, auth=auth) as client:
            response = await client.post(
                url,
                content=turtle_data.encode("utf-8"),
                headers=headers,
            )
            
            if response.status_code in (200, 201, 204):
                return LoadResult(
                    success=True,
                    triple_count=triple_count,
                    graph_uri=graph_uri,
                    message=f"Successfully loaded {triple_count} triples",
                )
            
            # Fallback to SPARQL UPDATE if Graph Store Protocol fails
            if response.status_code in (404, 405):
                logger.warning(
                    "Graph Store Protocol failed, falling back to SPARQL UPDATE",
                    status=response.status_code,
                    graph_uri=graph_uri,
                )
                return await self._load_via_sparql_update(turtle_data, graph_uri, triple_count)
            else:
                return LoadResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                )
    
    async def _load_via_sparql_update(
        self, 
        turtle_data: str, 
        graph_uri: str | None, 
        triple_count: int
    ) -> LoadResult:
        """Load Turtle data using SPARQL UPDATE INSERT DATA."""
        # Parse the Turtle data into a graph to extract triples
        g = Graph()
        g.parse(data=turtle_data, format="turtle")
        
        # Build SPARQL INSERT DATA from parsed triples
        # Convert each triple to SPARQL format
        triple_lines = []
        for s, p, o in g:
            # Format subject
            if isinstance(s, URIRef):
                subj = f"<{s}>"
            else:
                subj = str(s)
            
            # Format predicate
            if isinstance(p, URIRef):
                pred = f"<{p}>"
            else:
                pred = str(p)
            
            # Format object
            if isinstance(o, URIRef):
                obj = f"<{o}>"
            elif isinstance(o, Literal):
                # Escape quotes and handle language/datatype
                val = str(o).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                if o.language:
                    obj = f'"{val}"@{o.language}'
                elif o.datatype:
                    obj = f'"{val}"^^<{o.datatype}>'
                else:
                    obj = f'"{val}"'
            else:
                obj = str(o)
            
            triple_lines.append(f"{subj} {pred} {obj} .")
        
        # Build INSERT DATA statement
        triples_block = "\n                ".join(triple_lines)
        
        if graph_uri:
            update = f"""
            INSERT DATA {{
                GRAPH <{graph_uri}> {{
                    {triples_block}
                }}
            }}
            """
        else:
            update = f"""
            INSERT DATA {{
                {triples_block}
            }}
            """
        
        auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            auth = (self.settings.fuseki_user, self.settings.fuseki_password)
        
        async with httpx.AsyncClient(timeout=60.0, auth=auth) as client:
            # SPARQL UPDATE uses form-encoded data
            response = await client.post(
                self.update_endpoint,
                data={"update": update},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code in (200, 204):
                return LoadResult(
                    success=True,
                    triple_count=triple_count,
                    graph_uri=graph_uri,
                    message=f"Successfully loaded {triple_count} triples via SPARQL UPDATE",
                )
            else:
                return LoadResult(
                    success=False,
                    error=f"SPARQL UPDATE failed: HTTP {response.status_code}: {response.text[:500]}",
                )

    async def load_file(self, file_path: str, graph_uri: str | None = None) -> LoadResult:
        """Load RDF data from a file."""
        from pathlib import Path
        
        path = Path(file_path)
        if not path.exists():
            return LoadResult(
                success=False,
                error=f"File not found: {file_path}",
            )
        
        # Determine format from extension
        ext = path.suffix.lower()
        format_map = {
            ".ttl": "turtle",
            ".turtle": "turtle",
            ".rdf": "xml",
            ".xml": "xml",
            ".jsonld": "json-ld",
            ".json": "json-ld",
            ".nt": "nt",
            ".n3": "n3",
        }
        
        rdf_format = format_map.get(ext, "turtle")
        
        try:
            g = Graph()
            g.parse(file_path, format=rdf_format)
            turtle_data = g.serialize(format="turtle")
            
            return await self._load_turtle(turtle_data, graph_uri)
            
        except Exception as e:
            return LoadResult(
                success=False,
                error=f"Failed to parse file: {str(e)}",
            )

    async def clear_graph(self, graph_uri: str | None = None) -> bool:
        """Clear a graph (or default graph)."""
        if graph_uri:
            update = f"CLEAR GRAPH <{graph_uri}>"
        else:
            update = "CLEAR DEFAULT"
        
        auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            auth = (self.settings.fuseki_user, self.settings.fuseki_password)
        
        async with httpx.AsyncClient(timeout=30.0, auth=auth) as client:
            response = await client.post(
                self.update_endpoint,
                data={"update": update},
            )
            return response.status_code in (200, 204)

    async def drop_graph(self, graph_uri: str) -> bool:
        """Drop a named graph."""
        update = f"DROP GRAPH <{graph_uri}>"
        
        auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            auth = (self.settings.fuseki_user, self.settings.fuseki_password)
        
        async with httpx.AsyncClient(timeout=30.0, auth=auth) as client:
            response = await client.post(
                self.update_endpoint,
                data={"update": update},
            )
            return response.status_code in (200, 204)

    async def get_graph_count(self) -> int:
        """Get the number of triples in the default graph."""
        query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
        
        auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            auth = (self.settings.fuseki_user, self.settings.fuseki_password)
        
        async with httpx.AsyncClient(timeout=30.0, auth=auth) as client:
            response = await client.get(
                self.query_endpoint,
                params={"query": query},
                headers={"Accept": "application/sparql-results+json"},
            )
            
            if response.status_code == 200:
                data = response.json()
                bindings = data.get("results", {}).get("bindings", [])
                if bindings:
                    return int(bindings[0]["count"]["value"])
        
        return 0

    async def health_check(self) -> bool:
        """Check if Fuseki is accessible."""
        try:
            auth = None
            if self.settings.fuseki_user and self.settings.fuseki_password:
                auth = (self.settings.fuseki_user, self.settings.fuseki_password)
            
            async with httpx.AsyncClient(timeout=5.0, auth=auth) as client:
                response = await client.get(self.settings.fuseki_url)
                return response.status_code in (200, 302)
        except Exception:
            return False

    async def load_batch(
        self,
        items: list[dict[str, Any]],
    ) -> list[LoadResult]:
        """
        Load multiple RDF items in batch.
        
        Args:
            items: List of dicts with 'rdf_data' or 'graph' and optional 'graph_uri'
            
        Returns:
            List of LoadResult objects
        """
        results = []
        for item in items:
            result = await self.process(item)
            results.append(result)
        return results

    async def insert_triples(self, triples: list[tuple[str, str, str]]) -> LoadResult:
        """
        Insert individual triples using SPARQL UPDATE.
        
        Args:
            triples: List of (subject, predicate, object) tuples as URIs/literals
            
        Returns:
            LoadResult
        """
        if not triples:
            return LoadResult(success=True, triple_count=0, message="No triples to insert")
        
        # Build INSERT DATA statement
        triple_strings = []
        for s, p, o in triples:
            # Basic escaping
            if o.startswith("http://") or o.startswith("https://"):
                triple_strings.append(f"<{s}> <{p}> <{o}> .")
            else:
                escaped_o = o.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                triple_strings.append(f'<{s}> <{p}> "{escaped_o}" .')
        
        update = f"""
            INSERT DATA {{
                {chr(10).join(triple_strings)}
            }}
        """
        
        auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            auth = (self.settings.fuseki_user, self.settings.fuseki_password)
        
        async with httpx.AsyncClient(timeout=60.0, auth=auth) as client:
            response = await client.post(
                self.update_endpoint,
                data={"update": update},
            )
            
            if response.status_code in (200, 204):
                return LoadResult(
                    success=True,
                    triple_count=len(triples),
                    message=f"Inserted {len(triples)} triples",
                )
            else:
                return LoadResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                )
