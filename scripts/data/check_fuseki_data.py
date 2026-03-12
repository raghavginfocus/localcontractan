#!/usr/bin/env python3
"""
Check if Fuseki has data.

Usage:
    cd agents
    PYTHONPATH=src uv run python ../scripts/check_fuseki_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from fuseki_client import FusekiClient
from config import get_settings


def _check_dataset(client, settings, dataset_label: str):
    """Run triple/graph/contract/clause stats for a given client (dataset)."""
    try:
        query = """
        SELECT (COUNT(*) as ?count)
        WHERE { GRAPH ?g { ?s ?p ?o } }
        """
        results = client.execute_select(query)
        total_triples = int(results[0].get("count", 0)) if results else 0
        print(f"   ✅ Total triples: {total_triples:,}")
        if total_triples == 0:
            print(f"   ⚠️  Dataset is EMPTY")
            return
    except Exception as e:
        print(f"   ❌ Error counting triples: {e}")
        return
    try:
        query = """
        SELECT DISTINCT ?graph (COUNT(*) as ?count)
        WHERE { GRAPH ?graph { ?s ?p ?o } }
        GROUP BY ?graph
        ORDER BY DESC(?count)
        """
        results = client.execute_select(query)
        if results:
            print(f"   📦 Named graphs: {len(results)}")
            for i, r in enumerate(results[:5], 1):
                graph = r.get("graph", "N/A")
                count = int(r.get("count", 0))
                if "#graph/" in str(graph):
                    doc_id = str(graph).split("#graph/")[-1]
                    print(f"      {i}. {doc_id}: {count:,} triples")
                else:
                    graph_short = str(graph)[:60] + "..." if len(str(graph)) > 60 else str(graph)
                    print(f"      {i}. {graph_short}: {count:,} triples")
            if len(results) > 5:
                print(f"      ... and {len(results) - 5} more graph(s)")
    except Exception as e:
        print(f"   ⚠️  Could not retrieve named graphs: {e}")
    try:
        query = """
        PREFIX proc: <http://procurement.kg/ontology#>
        SELECT (COUNT(DISTINCT ?contract) as ?count)
        WHERE { GRAPH ?g { ?contract a proc:Contract . } }
        """
        results = client.execute_select(query)
        if results:
            print(f"   📄 Contracts: {int(results[0].get('count', 0))}")
    except Exception as e:
        print(f"   ⚠️  Could not count contracts: {e}")
    try:
        query = """
        PREFIX proc: <http://procurement.kg/ontology#>
        SELECT (COUNT(DISTINCT ?clause) as ?count)
        WHERE { GRAPH ?g { ?clause a proc:Clause . } }
        """
        results = client.execute_select(query)
        if results:
            print(f"   📝 Clauses: {int(results[0].get('count', 0))}")
    except Exception as e:
        print(f"   ⚠️  Could not count clauses: {e}")


def main():
    """Check if Fuseki has data (default + Docling dataset)."""
    settings = get_settings()
    
    print("\n" + "=" * 70)
    print("🔍 CHECKING FUSEKI DATA")
    print("=" * 70)
    
    # Connect to Fuseki - default dataset
    try:
        client = FusekiClient(settings=settings)
        print(f"\n✅ Connected to Fuseki at {settings.fuseki_url}")
        print(f"   Dataset: {settings.fuseki_dataset}")
    except Exception as e:
        print(f"\n❌ Failed to connect to Fuseki: {e}")
        return
    
    # Default dataset
    print(f"\n{'─' * 70}")
    print(f"📊 Dataset: {settings.fuseki_dataset} (default/legacy)")
    print(f"{'─' * 70}")
    _check_dataset(client, settings, settings.fuseki_dataset)
    
    # Docling dataset
    print(f"\n{'─' * 70}")
    print(f"📊 Dataset: {settings.docling_fuseki_dataset} (Docling)")
    print(f"{'─' * 70}")
    try:
        settings_docling = settings.model_copy(update={"fuseki_dataset": settings.docling_fuseki_dataset})
        client_docling = FusekiClient(settings=settings_docling)
        _check_dataset(client_docling, settings_docling, settings.docling_fuseki_dataset)
    except Exception as e:
        print(f"   ⚠️  Could not check Docling dataset: {e}")
        print(f"   (Dataset may not exist yet; create it in Fuseki or run Docling ingestion)")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("📊 SUMMARY")
    print(f"{'=' * 70}")
    
    try:
        query = """
        SELECT (COUNT(*) as ?count)
        WHERE { GRAPH ?g { ?s ?p ?o } }
        """
        results = client.execute_select(query)
        total = int(results[0].get("count", 0)) if results else 0
        if total > 0:
            print(f"✅ {settings.fuseki_dataset}: {total:,} triples")
        else:
            print(f"⚠️  {settings.fuseki_dataset}: empty")
        print(f"   (Docling dataset «{settings.docling_fuseki_dataset}» stats above)")
    except Exception as e:
        print(f"❌ Error getting summary: {e}")
    
    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
