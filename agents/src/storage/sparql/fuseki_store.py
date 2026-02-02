"""
Fuseki SPARQL Store Implementation

Concrete implementation of SPARQLStore for Apache Jena Fuseki.
"""

from typing import Any, Optional
from urllib.parse import quote

import httpx
from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD
from SPARQLWrapper import SPARQLWrapper, JSON, POST, DIGEST, BASIC, ASK

from config import Settings, get_settings
from storage.sparql.base import SPARQLStore
from storage.sparql.query_cache import get_query_cache
from logger import get_module_logger

logger = get_module_logger(__name__)


class FusekiStore(SPARQLStore):
    """
    SPARQL Store implementation for Apache Jena Fuseki.
    
    This is a wrapper around the existing FusekiClient functionality,
    implementing the SPARQLStore interface for abstraction.
    """

    # Common namespace prefixes
    PREFIXES = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX proc: <http://procurement.kg/ontology#>
        PREFIX contract: <http://procurement.kg/contract#>
    """

    def __init__(self, settings: Settings | None = None, enable_cache: bool = True):
        """Initialize the Fuseki store."""
        self.settings = settings or get_settings()
        self._query_endpoint = self.settings.sparql_query_endpoint
        self._update_endpoint = self.settings.sparql_update_endpoint
        self._graph_store_endpoint = self.settings.graph_store_endpoint

        # Set up authentication if credentials provided
        self.auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            self.auth = (self.settings.fuseki_user, self.settings.fuseki_password)
            logger.debug("Fuseki authentication configured", user=self.settings.fuseki_user)

        # Set up namespaces
        self.PROC = Namespace(self.settings.procurement_namespace)
        self.CONTRACT = Namespace(self.settings.contract_namespace)

        # Initialize query cache
        self.enable_cache = enable_cache
        self.query_cache = get_query_cache() if enable_cache else None

        logger.info(
            "FusekiStore initialized",
            query_endpoint=self._query_endpoint,
            update_endpoint=self._update_endpoint,
            cache_enabled=enable_cache,
        )

    @property
    def name(self) -> str:
        return "fuseki"

    @property
    def query_endpoint(self) -> str:
        return self._query_endpoint

    @property
    def update_endpoint(self) -> str:
        return self._update_endpoint

    @property
    def graph_store_endpoint(self) -> str:
        return self._graph_store_endpoint

    def validate_config(self) -> bool:
        """Validate Fuseki configuration."""
        return bool(self.settings.fuseki_url and self.settings.fuseki_dataset)

    def execute_select(
        self,
        query: str,
        add_prefixes: bool = True,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query with optional caching.
        
        Args:
            query: SPARQL query string
            add_prefixes: Whether to add standard prefixes
            use_cache: Whether to use query cache
            cache_ttl: Optional custom TTL for this query
        """
        full_query = f"{self.PREFIXES}\n{query}" if add_prefixes else query

        # Check cache first
        if use_cache and self.query_cache:
            cached_results = self.query_cache.get(full_query)
            if cached_results is not None:
                logger.debug("Cache hit for SPARQL query", result_count=len(cached_results))
                return cached_results

        sparql = SPARQLWrapper(self._query_endpoint)
        sparql.setQuery(full_query)
        sparql.setReturnFormat(JSON)

        if self.auth:
            sparql.setHTTPAuth(BASIC)
            sparql.setCredentials(self.auth[0], self.auth[1])

        try:
            response = sparql.query().convert()
            results = []

            for binding in response["results"]["bindings"]:
                row = {}
                for var, value in binding.items():
                    if value["type"] == "uri":
                        row[var] = value["value"]
                    elif value["type"] == "literal":
                        row[var] = value.get("value", "")
                    elif value["type"] == "typed-literal":
                        row[var] = value.get("value", "")
                    else:
                        row[var] = str(value.get("value", ""))
                results.append(row)

            # Cache the results
            if use_cache and self.query_cache:
                self.query_cache.set(full_query, results, ttl=cache_ttl)

            logger.debug("SPARQL SELECT executed", result_count=len(results), cached=False)
            return results

        except Exception as e:
            logger.error("SPARQL SELECT failed", error=str(e), query=query[:200])
            raise

    def execute_construct(self, query: str, add_prefixes: bool = True) -> Graph:
        """Execute a SPARQL CONSTRUCT query."""
        full_query = f"{self.PREFIXES}\n{query}" if add_prefixes else query

        sparql = SPARQLWrapper(self._query_endpoint)
        sparql.setQuery(full_query)
        sparql.setReturnFormat("rdf+xml")

        if self.auth:
            sparql.setHTTPAuth(BASIC)
            sparql.setCredentials(self.auth[0], self.auth[1])

        try:
            response = sparql.query().convert()
            graph = Graph()
            graph.parse(data=response.serialize(), format="xml")

            logger.debug("SPARQL CONSTRUCT executed", triple_count=len(graph))
            return graph

        except Exception as e:
            logger.error("SPARQL CONSTRUCT failed", error=str(e))
            raise

    def execute_update(self, update_query: str) -> bool:
        """Execute a SPARQL UPDATE operation."""
        full_update = f"{self.PREFIXES}\n{update_query}"

        sparql = SPARQLWrapper(self._update_endpoint)
        sparql.setQuery(full_update)
        sparql.setMethod(POST)

        if self.auth:
            sparql.setHTTPAuth(BASIC)
            sparql.setCredentials(self.auth[0], self.auth[1])

        try:
            sparql.query()
            logger.debug("SPARQL UPDATE executed")
            return True

        except Exception as e:
            logger.error("SPARQL UPDATE failed", error=str(e))
            raise

    def execute_ask(self, query: str, add_prefixes: bool = True) -> bool:
        """Execute a SPARQL ASK query."""
        full_query = f"{self.PREFIXES}\n{query}" if add_prefixes else query

        sparql = SPARQLWrapper(self._query_endpoint)
        sparql.setQuery(full_query)
        sparql.setReturnFormat(JSON)

        if self.auth:
            sparql.setHTTPAuth(BASIC)
            sparql.setCredentials(self.auth[0], self.auth[1])

        try:
            response = sparql.query().convert()
            result = response.get("boolean", False)
            logger.debug("SPARQL ASK executed", result=result)
            return result

        except Exception as e:
            logger.error("SPARQL ASK failed", error=str(e))
            raise

    def load_rdf(
        self,
        data: str,
        format: str = "turtle",
        graph_uri: str | None = None,
    ) -> bool:
        """Load RDF data into the store."""
        # Map format names
        content_type_map = {
            "turtle": "text/turtle",
            "ttl": "text/turtle",
            "json-ld": "application/ld+json",
            "jsonld": "application/ld+json",
            "xml": "application/rdf+xml",
            "rdf": "application/rdf+xml",
        }

        content_type = content_type_map.get(format.lower(), "text/turtle")
        headers = {"Content-Type": content_type}
        url = self._graph_store_endpoint

        if graph_uri:
            # URL-encode the graph_uri to handle special characters like #
            encoded_graph_uri = quote(graph_uri, safe="")
            url = f"{url}?graph={encoded_graph_uri}"

        try:
            with httpx.Client(timeout=30.0, auth=self.auth) as client:
                response = client.post(url, content=data.encode("utf-8"), headers=headers)

                if response.status_code in (200, 201, 204):
                    logger.info("RDF data loaded", graph_uri=graph_uri, format=format)
                    return True
                elif response.status_code == 405:
                    # Fallback to SPARQL UPDATE if GSP POST is not supported
                    logger.warning("GSP POST returned 405, attempting SPARQL UPDATE")
                    insert_update = f"""
                        INSERT DATA {{
                            GRAPH <{graph_uri}> {{
                                {data}
                            }}
                        }}
                    """
                    return self.execute_update(insert_update)
                else:
                    response.raise_for_status()
                    return False

        except Exception as e:
            logger.error("Failed to load RDF data", error=str(e), format=format)
            raise
