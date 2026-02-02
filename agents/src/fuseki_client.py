"""
Fuseki SPARQL Client for Python-Jena integration.

This module provides a clean Python interface to interact with the 
Apache Jena Fuseki SPARQL server.
"""

import json
from typing import Any

import httpx
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
from SPARQLWrapper import SPARQLWrapper, JSON, POST, DIGEST, BASIC

from config import Settings, get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class FusekiClient:
    """
    Client for interacting with Apache Jena Fuseki SPARQL server.
    
    Provides methods for:
    - Executing SPARQL SELECT queries
    - Executing SPARQL CONSTRUCT queries
    - Executing SPARQL UPDATE operations
    - Loading RDF data (Turtle, JSON-LD, RDF/XML)
    - Managing named graphs
    """

    # Common namespace prefixes
    PREFIXES = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX proc: <http://procurement.kg/ontology#>
        PREFIX contract: <http://procurement.kg/contract#>
        PREFIX text: <http://jena.apache.org/text#>
    """

    def __init__(self, settings: Settings | None = None):
        """Initialize the Fuseki client."""
        self.settings = settings or get_settings()
        self.query_endpoint = self.settings.sparql_query_endpoint
        self.update_endpoint = self.settings.sparql_update_endpoint
        self.graph_store_endpoint = self.settings.graph_store_endpoint
        
        # Set up authentication if credentials provided
        self.auth = None
        if self.settings.fuseki_user and self.settings.fuseki_password:
            self.auth = (self.settings.fuseki_user, self.settings.fuseki_password)
            logger.debug("Fuseki authentication configured", user=self.settings.fuseki_user)
        
        # Set up namespaces
        self.PROC = Namespace(self.settings.procurement_namespace)
        self.CONTRACT = Namespace(self.settings.contract_namespace)
        
        logger.info(
            "FusekiClient initialized",
            query_endpoint=self.query_endpoint,
            update_endpoint=self.update_endpoint,
        )

    def execute_select(self, query: str, add_prefixes: bool = True) -> list[dict[str, Any]]:
        """
        Execute a SPARQL SELECT query and return results as list of dicts.
        
        Args:
            query: SPARQL SELECT query
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            List of dictionaries with variable bindings
        """
        full_query = f"{self.PREFIXES}\n{query}" if add_prefixes else query
        
        sparql = SPARQLWrapper(self.query_endpoint)
        sparql.setQuery(full_query)
        sparql.setReturnFormat(JSON)
        
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
            
            logger.debug("SPARQL SELECT executed", result_count=len(results))
            return results
            
        except Exception as e:
            logger.error("SPARQL SELECT failed", error=str(e), query=query[:200])
            raise

    def execute_construct(self, query: str, add_prefixes: bool = True) -> Graph:
        """
        Execute a SPARQL CONSTRUCT query and return an RDFLib Graph.
        
        Args:
            query: SPARQL CONSTRUCT query
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            RDFLib Graph with constructed triples
        """
        full_query = f"{self.PREFIXES}\n{query}" if add_prefixes else query
        
        sparql = SPARQLWrapper(self.query_endpoint)
        sparql.setQuery(full_query)
        sparql.setReturnFormat("rdf+xml")
        
        try:
            response = sparql.query().convert()
            graph = Graph()
            graph.parse(data=response.serialize(), format="xml")
            
            logger.debug("SPARQL CONSTRUCT executed", triple_count=len(graph))
            return graph
            
        except Exception as e:
            logger.error("SPARQL CONSTRUCT failed", error=str(e))
            raise

    def execute_ask(self, query: str, add_prefixes: bool = True) -> bool:
        """
        Execute a SPARQL ASK query and return boolean result.
        
        Args:
            query: SPARQL ASK query
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            Boolean result of the ASK query
        """
        full_query = f"{self.PREFIXES}\n{query}" if add_prefixes else query
        
        sparql = SPARQLWrapper(self.query_endpoint)
        sparql.setQuery(full_query)
        sparql.setReturnFormat(JSON)
        
        try:
            response = sparql.query().convert()
            result = response.get("boolean", False)
            logger.debug("SPARQL ASK executed", result=result)
            return result
            
        except Exception as e:
            logger.error("SPARQL ASK failed", error=str(e))
            raise

    def execute_update(self, update: str, add_prefixes: bool = True) -> bool:
        """
        Execute a SPARQL UPDATE operation.
        
        Args:
            update: SPARQL UPDATE statement
            add_prefixes: Whether to prepend common prefixes
            
        Returns:
            True if successful
        """
        full_update = f"{self.PREFIXES}\n{update}" if add_prefixes else update
        
        sparql = SPARQLWrapper(self.update_endpoint)
        sparql.setQuery(full_update)
        sparql.setMethod(POST)
        
        # Set authentication if available
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

    def load_turtle(self, turtle_data: str, graph_uri: str | None = None) -> bool:
        """
        Load Turtle RDF data into the triple store.
        
        Args:
            turtle_data: RDF data in Turtle format
            graph_uri: Optional named graph URI
            
        Returns:
            True if successful
        """
        headers = {"Content-Type": "text/turtle"}
        url = self.graph_store_endpoint
        
        if graph_uri:
            url = f"{url}?graph={graph_uri}"
        
        try:
            with httpx.Client(timeout=30.0, auth=self.auth) as client:
                response = client.post(url, content=turtle_data, headers=headers)
                response.raise_for_status()
            
            logger.info("Turtle data loaded", graph_uri=graph_uri)
            return True
            
        except Exception as e:
            logger.error("Failed to load Turtle data", error=str(e))
            raise

    def load_graph(self, graph: Graph, graph_uri: str | None = None) -> bool:
        """
        Load an RDFLib Graph into the triple store.
        
        Args:
            graph: RDFLib Graph to load
            graph_uri: Optional named graph URI
            
        Returns:
            True if successful
        """
        turtle_data = graph.serialize(format="turtle")
        return self.load_turtle(turtle_data, graph_uri)

    def insert_contract(
        self,
        contract_id: str,
        value: float | None = None,
        effective_date: str | None = None,
        expiration_date: str | None = None,
        jurisdiction: str | None = None,
    ) -> str:
        """
        Insert a new contract into the knowledge graph.
        
        Args:
            contract_id: Unique identifier for the contract
            value: Contract value
            effective_date: ISO date string
            expiration_date: ISO date string
            jurisdiction: Jurisdiction URI (e.g., 'EU', 'US')
            
        Returns:
            URI of the created contract
        """
        contract_uri = f"{self.settings.contract_namespace}{contract_id}"
        proc_ns = self.settings.procurement_namespace
        
        # Build INSERT DATA statement
        triples = [f"<{contract_uri}> rdf:type proc:Contract ."]
        
        if value is not None:
            triples.append(f'<{contract_uri}> proc:contractValue "{value}"^^xsd:decimal .')
        
        if effective_date:
            triples.append(f'<{contract_uri}> proc:effectiveDate "{effective_date}"^^xsd:date .')
        
        if expiration_date:
            triples.append(f'<{contract_uri}> proc:expirationDate "{expiration_date}"^^xsd:date .')
        
        if jurisdiction:
            jurisdiction_uri = f"{proc_ns}{jurisdiction}"
            triples.append(f"<{contract_uri}> proc:governedBy <{jurisdiction_uri}> .")
        
        update = f"""
            INSERT DATA {{
                {chr(10).join(triples)}
            }}
        """
        
        self.execute_update(update)
        logger.info("Contract inserted", contract_uri=contract_uri)
        
        return contract_uri

    def insert_clause(
        self,
        clause_id: str,
        contract_uri: str,
        clause_type: str,
        raw_text: str,
        notice_period: int | None = None,
    ) -> str:
        """
        Insert a clause into the knowledge graph.
        
        Args:
            clause_id: Unique identifier for the clause
            contract_uri: URI of the parent contract
            clause_type: Type of clause (e.g., 'TerminationClause')
            raw_text: Original text of the clause
            notice_period: For termination clauses, the notice period in days
            
        Returns:
            URI of the created clause
        """
        clause_uri = f"{self.settings.contract_namespace}{clause_id}"
        proc_ns = self.settings.procurement_namespace
        
        # Escape raw text for SPARQL
        escaped_text = raw_text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        
        triples = [
            f"<{clause_uri}> rdf:type proc:{clause_type} .",
            f"<{contract_uri}> proc:hasClause <{clause_uri}> .",
            f'<{clause_uri}> proc:rawText "{escaped_text}" .',
        ]
        
        if notice_period is not None:
            triples.append(f'<{clause_uri}> proc:noticePeriod "{notice_period}"^^xsd:integer .')
        
        update = f"""
            INSERT DATA {{
                {chr(10).join(triples)}
            }}
        """
        
        self.execute_update(update)
        logger.info("Clause inserted", clause_uri=clause_uri, clause_type=clause_type)
        
        return clause_uri

    def get_contract_risks(self, contract_uri: str) -> list[dict[str, Any]]:
        """
        Get all risks associated with a contract's clauses.
        
        Args:
            contract_uri: URI of the contract
            
        Returns:
            List of risk information dicts
        """
        query = f"""
            SELECT ?clause ?clauseType ?risk ?riskLabel
            WHERE {{
                <{contract_uri}> proc:hasClause ?clause .
                ?clause rdf:type ?clauseType .
                ?clause proc:introducesRisk ?risk .
                OPTIONAL {{ ?risk rdfs:label ?riskLabel }}
            }}
        """
        return self.execute_select(query)

    def get_compliance_issues(self, contract_uri: str) -> list[dict[str, Any]]:
        """
        Get all compliance issues for a contract.
        
        Args:
            contract_uri: URI of the contract
            
        Returns:
            List of compliance issue dicts
        """
        query = f"""
            SELECT ?issue ?issueLabel
            WHERE {{
                <{contract_uri}> proc:hasComplianceIssue ?issue .
                OPTIONAL {{ ?issue rdfs:label ?issueLabel }}
            }}
        """
        return self.execute_select(query)

    def search_contracts(
        self,
        jurisdiction: str | None = None,
        min_value: float | None = None,
        has_risk: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search contracts with various filters.
        
        Args:
            jurisdiction: Filter by jurisdiction
            min_value: Minimum contract value
            has_risk: Filter by risk type
            
        Returns:
            List of matching contracts
        """
        filters = []
        
        if jurisdiction:
            filters.append(f"?contract proc:governedBy proc:{jurisdiction} .")
        
        if min_value is not None:
            filters.append(f"""
                ?contract proc:contractValue ?value .
                FILTER(?value >= {min_value})
            """)
        
        if has_risk:
            filters.append(f"""
                ?contract proc:hasClause ?clause .
                ?clause proc:introducesRisk proc:{has_risk} .
            """)
        
        filter_clause = "\n".join(filters) if filters else ""
        
        query = f"""
            SELECT DISTINCT ?contract ?value ?jurisdiction
            WHERE {{
                ?contract rdf:type proc:Contract .
                {filter_clause}
                OPTIONAL {{ ?contract proc:contractValue ?value }}
                OPTIONAL {{ ?contract proc:governedBy ?jurisdiction }}
            }}
            ORDER BY ?contract
        """
        
        return self.execute_select(query)

    def get_triple_count(self, graph_uri: str | None = None) -> int:
        """
        Get the total number of triples in a graph.
        
        Args:
            graph_uri: Optional named graph URI. If None, counts default graph.
            
        Returns:
            Number of triples
        """
        if graph_uri:
            query = f"""
                SELECT (COUNT(*) as ?count)
                WHERE {{
                    GRAPH <{graph_uri}> {{
                        ?s ?p ?o
                    }}
                }}
            """
        else:
            query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
        
        results = self.execute_select(query, add_prefixes=False)
        return int(results[0]["count"]) if results else 0

    def delete_graph(self, graph_uri: str) -> bool:
        """
        Delete all triples from a named graph.
        
        Args:
            graph_uri: URI of the graph to delete
            
        Returns:
            True if successful
        """
        update = f"""
            DROP SILENT GRAPH <{graph_uri}>
        """
        
        try:
            self.execute_update(update, add_prefixes=False)
            logger.info("Graph deleted", graph_uri=graph_uri)
            return True
        except Exception as e:
            logger.error("Failed to delete graph",
                        graph_uri=graph_uri, error=str(e))
            raise

    def list_graphs(self) -> list[str]:
        """
        List all named graphs in the dataset.
        
        Returns:
            List of graph URIs
        """
        query = """
            SELECT DISTINCT ?g
            WHERE {
                GRAPH ?g { ?s ?p ?o }
            }
        """
        
        results = self.execute_select(query, add_prefixes=False)
        return [row['g'] for row in results]

    def health_check(self) -> bool:
        """Check if Fuseki server is accessible."""
        try:
            self.get_triple_count()
            return True
        except Exception:
            return False

    def text_search(
        self,
        search_term: str,
        field: str = "text",
        clause_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Fast text search using jena-text index.
        
        Args:
            search_term: Text to search for
            field: Which field to search ("text", "summary", "keyPoint")
            clause_type: Optional clause type filter (e.g., "TerminationClause")
            limit: Maximum results to return
            
        Returns:
            List of clauses matching the search term
        """
        # Map field names to predicates
        field_map = {
            "text": "proc:rawText",
            "summary": "proc:summary",
            "keyPoint": "proc:hasKeyPoint",
        }
        
        predicate = field_map.get(field, "proc:rawText")
        
        # Build query
        query = f"""
        SELECT ?clause ?text ?summary WHERE {{
            ?clause text:query ({predicate} "{search_term}") .
            OPTIONAL {{ ?clause proc:rawText ?text }}
            OPTIONAL {{ ?clause proc:summary ?summary }}
        """
        
        if clause_type:
            query += f"    ?clause a proc:{clause_type} .\n"
        
        query += f"}} LIMIT {limit}"
        
        return self.execute_select(query)
