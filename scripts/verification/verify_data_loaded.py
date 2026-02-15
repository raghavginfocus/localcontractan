#!/usr/bin/env python3
"""
Verify that data was loaded into Fuseki and Milvus.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents/src"))

from config import get_settings
from SPARQLWrapper import SPARQLWrapper, JSON
import requests

def check_fuseki():
    """Check if data exists in Fuseki."""
    settings = get_settings()
    
    print("=" * 60)
    print("CHECKING FUSEKI")
    print("=" * 60)
    
    # Check datasets
    try:
        response = requests.get(f"{settings.fuseki_url}/$/datasets", timeout=5)
        print(f"\n✓ Fuseki is running at {settings.fuseki_url}")
        print(f"  Response: {response.status_code}")
    except Exception as e:
        print(f"\n✗ Cannot connect to Fuseki: {e}")
        return False
    
    # Try to query the dataset
    sparql = SPARQLWrapper(f"{settings.fuseki_url}/{settings.fuseki_dataset}/query")
    sparql.setReturnFormat(JSON)
    
    # Count total triples across ALL graphs (including named graphs)
    sparql.setQuery("SELECT (COUNT(*) as ?count) WHERE { GRAPH ?g { ?s ?p ?o } }")
    try:
        results = sparql.query().convert()
        count = int(results["results"]["bindings"][0]["count"]["value"])
        print(f"\n✓ Total triples in named graphs: {count:,}")
        
        if count == 0:
            print("  ⚠️  WARNING: No triples found in named graphs!")
            return False
    except Exception as e:
        print(f"\n✗ Named graph query failed: {e}")
        return False
    
    # Also count default graph triples
    sparql.setQuery("SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }")
    try:
        results = sparql.query().convert()
        default_count = int(results["results"]["bindings"][0]["count"]["value"])
        print(f"✓ Total triples in default graph: {default_count:,}")
        print(f"✓ GRAND TOTAL: {count + default_count:,} triples")
    except Exception as e:
        print(f"✗ Default graph query failed: {e}")
    
    # Count contracts in named graphs
    sparql.setQuery("""
        PREFIX proc: <http://procurement.kg/ontology#>
        SELECT (COUNT(DISTINCT ?contract) as ?count)
        WHERE {
            GRAPH ?g {
                ?contract a proc:Contract
            }
        }
    """)
    try:
        results = sparql.query().convert()
        count = int(results["results"]["bindings"][0]["count"]["value"])
        print(f"✓ Contracts found: {count}")
    except Exception as e:
        print(f"✗ Contract query failed: {e}")
    
    # Count clauses in named graphs
    sparql.setQuery("""
        PREFIX proc: <http://procurement.kg/ontology#>
        SELECT (COUNT(DISTINCT ?clause) as ?count)
        WHERE {
            GRAPH ?g {
                ?clause a ?type .
                FILTER(CONTAINS(STR(?type), "Clause"))
            }
        }
    """)
    try:
        results = sparql.query().convert()
        count = int(results["results"]["bindings"][0]["count"]["value"])
        print(f"✓ Clauses found: {count}")
    except Exception as e:
        print(f"✗ Clause query failed: {e}")
    
    # Check ontology classes
    sparql.setQuery("""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?class) as ?count)
        WHERE {
            ?class a owl:Class
        }
    """)
    try:
        results = sparql.query().convert()
        count = int(results["results"]["bindings"][0]["count"]["value"])
        print(f"✓ Ontology classes defined: {count}")
    except Exception as e:
        print(f"✗ Ontology query failed: {e}")
    
    # Check for SHACL shapes
    sparql.setQuery("""
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT (COUNT(DISTINCT ?shape) as ?count)
        WHERE {
            ?shape a sh:NodeShape
        }
    """)
    try:
        results = sparql.query().convert()
        count = int(results["results"]["bindings"][0]["count"]["value"])
        print(f"✓ SHACL shapes defined: {count}")
    except Exception as e:
        print(f"✗ SHACL query failed: {e}")
    
    # List named graphs
    sparql.setQuery("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")
    try:
        results = sparql.query().convert()
        graphs = [b["g"]["value"] for b in results["results"]["bindings"]]
        print(f"\n✓ Named graphs ({len(graphs)}):")
        for g in graphs[:10]:  # Show first 10
            print(f"  - {g}")
        if len(graphs) > 10:
            print(f"  ... and {len(graphs) - 10} more")
    except Exception as e:
        print(f"✗ Graph query failed: {e}")
    
    return True

def check_milvus():
    """Check if vectors exist in Milvus."""
    settings = get_settings()
    
    print("\n" + "=" * 60)
    print("CHECKING MILVUS")
    print("=" * 60)
    
    try:
        from pymilvus import connections, Collection
        
        # Connect
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port
        )
        print(f"\n✓ Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}")
        
        # Check collection - use v2 collection
        collection_name = settings.milvus_collection_v2
        try:
            collection = Collection(collection_name)
            collection.load()
            
            count = collection.num_entities
            print(f"✓ Collection '{collection_name}' exists")
            print(f"✓ Vector count: {count:,}")
            
            if count == 0:
                print("  ⚠️  WARNING: No vectors found!")
                return False
            
            return True
        except Exception as e:
            print(f"✗ Collection '{collection_name}' not found or error: {e}")
            return False
            
    except ImportError:
        print("✗ pymilvus not installed")
        return False
    except Exception as e:
        print(f"✗ Cannot connect to Milvus: {e}")
        return False

if __name__ == "__main__":
    print("\n🔍 VERIFYING DATA INGESTION\n")
    
    fuseki_ok = check_fuseki()
    milvus_ok = check_milvus()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Fuseki: {'✓ OK' if fuseki_ok else '✗ FAILED'}")
    print(f"Milvus: {'✓ OK' if milvus_ok else '✗ FAILED'}")
    
    if fuseki_ok and milvus_ok:
        print("\n✅ All systems verified - data successfully loaded!")
        sys.exit(0)
    else:
        print("\n❌ Verification failed - check logs for details")
        sys.exit(1)


