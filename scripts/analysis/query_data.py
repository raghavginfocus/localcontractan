#!/usr/bin/env python3
"""
Query Data from Fuseki

Run SPARQL queries against the contract knowledge graph.
Supports both pre-built queries and custom SPARQL.

Usage:
    uv run python query_data.py                    # Interactive mode
    uv run python query_data.py --list-contracts   # List all contracts
    uv run python query_data.py --list-clauses     # List all clauses
    uv run python query_data.py --high-risk        # Find high-risk items
    uv run python query_data.py --query "SELECT..."  # Custom query
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

# Configuration
FUSEKI_URL = "http://localhost:3030"
DATASET = "contracts"

# SPARQL Prefixes
PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX proc: <http://procurement.kg/ontology#>
PREFIX contract: <http://procurement.kg/contract#>
"""

# Pre-built queries
QUERIES = {
    "count": """
        SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }
    """,
    
    "list-contracts": """
        SELECT ?contract ?label ?value ?jurisdiction WHERE {
            ?contract a proc:Contract .
            OPTIONAL { ?contract rdfs:label ?label }
            OPTIONAL { ?contract proc:contractValue ?value }
            OPTIONAL { ?contract proc:governedBy ?jurisdiction }
        }
        ORDER BY ?contract
    """,
    
    "list-clauses": """
        SELECT ?contract ?clause ?clauseType ?noticePeriod WHERE {
            ?contract proc:hasClause ?clause .
            ?clause a ?clauseType .
            FILTER(?clauseType != owl:NamedIndividual)
            OPTIONAL { ?clause proc:noticePeriod ?noticePeriod }
        }
        ORDER BY ?contract ?clause
    """,
    
    "termination-clauses": """
        SELECT ?contract ?clause ?noticePeriod ?text WHERE {
            ?contract proc:hasClause ?clause .
            ?clause a proc:TerminationClause .
            OPTIONAL { ?clause proc:noticePeriod ?noticePeriod }
            OPTIONAL { ?clause proc:rawText ?text }
        }
        ORDER BY ?noticePeriod
    """,
    
    "high-risk": """
        SELECT ?contract ?contractLabel ?clause ?risk WHERE {
            ?contract a proc:Contract .
            ?contract proc:hasClause ?clause .
            ?clause proc:introducesRisk ?risk .
            OPTIONAL { ?contract rdfs:label ?contractLabel }
        }
    """,
    
    "compliance-issues": """
        SELECT ?contract ?contractLabel ?issue WHERE {
            ?contract a proc:Contract .
            ?contract proc:hasComplianceIssue ?issue .
            OPTIONAL { ?contract rdfs:label ?contractLabel }
        }
    """,
    
    "by-jurisdiction": """
        SELECT ?jurisdiction (COUNT(?contract) as ?count) WHERE {
            ?contract a proc:Contract .
            ?contract proc:governedBy ?jurisdiction .
        }
        GROUP BY ?jurisdiction
        ORDER BY DESC(?count)
    """,
    
    "high-value": """
        SELECT ?contract ?label ?value WHERE {
            ?contract a proc:Contract .
            ?contract proc:contractValue ?value .
            OPTIONAL { ?contract rdfs:label ?label }
            FILTER(?value >= 1000000)
        }
        ORDER BY DESC(?value)
    """,
    
    "ontology-classes": """
        SELECT DISTINCT ?class ?label WHERE {
            ?class a owl:Class .
            OPTIONAL { ?class rdfs:label ?label }
        }
        ORDER BY ?class
    """,
    
    "ontology-properties": """
        SELECT DISTINCT ?prop ?label ?domain ?range WHERE {
            { ?prop a owl:ObjectProperty } UNION { ?prop a owl:DatatypeProperty }
            OPTIONAL { ?prop rdfs:label ?label }
            OPTIONAL { ?prop rdfs:domain ?domain }
            OPTIONAL { ?prop rdfs:range ?range }
        }
        ORDER BY ?prop
    """,
}


def execute_query(query: str, output_format: str = "table") -> list[dict]:
    """Execute a SPARQL query and return results."""
    full_query = PREFIXES + query
    
    response = httpx.post(
        f"{FUSEKI_URL}/{DATASET}/query",
        data={"query": full_query},
        headers={"Accept": "application/json"},
        timeout=60.0,
    )
    
    if response.status_code != 200:
        print(f"❌ Query failed: {response.status_code}")
        print(response.text[:500])
        return []
    
    data = response.json()
    results = []
    
    for binding in data.get("results", {}).get("bindings", []):
        row = {}
        for var, value in binding.items():
            if value["type"] == "uri":
                # Shorten URIs for display
                uri = value["value"]
                if "#" in uri:
                    row[var] = uri.split("#")[-1]
                elif "/" in uri:
                    row[var] = uri.split("/")[-1]
                else:
                    row[var] = uri
            else:
                row[var] = value.get("value", "")
        results.append(row)
    
    return results


def print_results(results: list[dict], output_format: str = "table"):
    """Print query results in various formats."""
    if not results:
        print("No results found.")
        return
    
    if output_format == "json":
        print(json.dumps(results, indent=2))
        return
    
    if output_format == "csv":
        headers = results[0].keys()
        print(",".join(headers))
        for row in results:
            print(",".join(str(row.get(h, "")) for h in headers))
        return
    
    # Table format (default)
    headers = list(results[0].keys())
    
    # Calculate column widths
    widths = {h: len(h) for h in headers}
    for row in results:
        for h in headers:
            val = str(row.get(h, ""))
            widths[h] = max(widths[h], min(len(val), 50))  # Cap at 50
    
    # Print header
    header_line = " | ".join(h.ljust(widths[h]) for h in headers)
    print(header_line)
    print("-" * len(header_line))
    
    # Print rows
    for row in results:
        values = []
        for h in headers:
            val = str(row.get(h, ""))
            if len(val) > 50:
                val = val[:47] + "..."
            values.append(val.ljust(widths[h]))
        print(" | ".join(values))
    
    print(f"\n({len(results)} results)")


def interactive_mode():
    """Interactive SPARQL query mode."""
    print("🔍 Interactive SPARQL Query Mode")
    print("   Type 'help' for available commands")
    print("   Type 'exit' or Ctrl+C to quit")
    print()
    
    while True:
        try:
            user_input = input("SPARQL> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "exit":
                break
            
            if user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  exit          - Quit")
                print("  help          - Show this help")
                print("  queries       - List pre-built queries")
                print("  run <name>    - Run a pre-built query")
                print("  <SPARQL>      - Execute custom SPARQL query")
                print()
                continue
            
            if user_input.lower() == "queries":
                print("\nPre-built queries:")
                for name in QUERIES.keys():
                    print(f"  - {name}")
                print("\nUse 'run <name>' to execute")
                print()
                continue
            
            if user_input.lower().startswith("run "):
                query_name = user_input[4:].strip()
                if query_name in QUERIES:
                    results = execute_query(QUERIES[query_name])
                    print_results(results)
                else:
                    print(f"Unknown query: {query_name}")
                continue
            
            # Execute as SPARQL
            results = execute_query(user_input)
            print_results(results)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    global DATASET
    
    parser = argparse.ArgumentParser(description="Query Fuseki data")
    parser.add_argument(
        "--dataset", "-d",
        default=DATASET,
        help=f"Dataset name (default: {DATASET})",
    )
    parser.add_argument(
        "--query", "-q",
        help="Custom SPARQL query",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive query mode",
    )
    
    # Pre-built query shortcuts
    for name in QUERIES.keys():
        parser.add_argument(
            f"--{name}",
            action="store_true",
            help=f"Run '{name}' query",
        )
    
    args = parser.parse_args()
    DATASET = args.dataset
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
        return
    
    # Custom query
    if args.query:
        results = execute_query(args.query)
        print_results(results, args.format)
        return
    
    # Check for pre-built query flags
    for name in QUERIES.keys():
        flag_name = name.replace("-", "_")
        if getattr(args, flag_name, False):
            print(f"📊 Running query: {name}")
            print()
            results = execute_query(QUERIES[name])
            print_results(results, args.format)
            return
    
    # Default: interactive mode
    interactive_mode()


if __name__ == "__main__":
    main()
