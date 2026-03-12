#!/usr/bin/env python3
"""
Check if Milvus collection with dimension 1024 has data.

Usage:
    cd agents
    PYTHONPATH=src uv run python ../scripts/check_milvus_data.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from pymilvus import connections, Collection, utility
from config import get_settings


def check_collection(collection_name: str, settings) -> dict:
    """Check a specific collection for data."""
    try:
        if not utility.has_collection(collection_name):
            return {
                "exists": False,
                "name": collection_name,
                "num_entities": 0,
                "dimension": None,
                "error": "Collection does not exist"
            }
        
        collection = Collection(collection_name)
        collection.load()
        
        # Get schema to check dimension
        schema = collection.schema
        embedding_dim = None
        for field in schema.fields:
            if field.name == "embedding" and hasattr(field, 'dim'):
                embedding_dim = field.dim
                break
        
        # Get entity count
        num_entities = collection.num_entities
        
        return {
            "exists": True,
            "name": collection_name,
            "num_entities": num_entities,
            "dimension": embedding_dim,
            "error": None
        }
    except Exception as e:
        return {
            "exists": False,
            "name": collection_name,
            "num_entities": 0,
            "dimension": None,
            "error": str(e)
        }


def main():
    """Check Milvus collections for data."""
    settings = get_settings()
    
    print("\n" + "=" * 70)
    print("🔍 CHECKING MILVUS COLLECTIONS (Dimension 1024)")
    print("=" * 70)
    
    # Connect to Milvus
    try:
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
        )
        print(f"\n✅ Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}")
    except Exception as e:
        print(f"\n❌ Failed to connect to Milvus: {e}")
        return
    
    # Check legacy, v2, and Docling collections
    collections_to_check = [
        settings.milvus_collection,  # v1
        settings.milvus_collection_v2,  # v2
        settings.docling_milvus_collection,  # Docling pipeline
    ]
    
    print(f"\n📋 Checking collections:")
    print(f"   • v1 (legacy): {settings.milvus_collection}")
    print(f"   • v2: {settings.milvus_collection_v2}")
    print(f"   • Docling: {settings.docling_milvus_collection}")
    print(f"   • Expected dimension: {settings.embedding_dim}")
    
    results = []
    for collection_name in collections_to_check:
        print(f"\n{'─' * 70}")
        print(f"📦 Collection: {collection_name}")
        print(f"{'─' * 70}")
        
        result = check_collection(collection_name, settings)
        results.append(result)
        
        if result["error"]:
            print(f"   ❌ Error: {result['error']}")
        elif not result["exists"]:
            print(f"   ⚠️  Collection does not exist")
        else:
            print(f"   ✅ Collection exists")
            print(f"   📊 Entities: {result['num_entities']:,}")
            print(f"   📐 Dimension: {result['dimension']}")
            
            if result["dimension"] == settings.embedding_dim:
                print(f"   ✅ Dimension matches expected ({settings.embedding_dim})")
            else:
                print(f"   ⚠️  Dimension mismatch! Expected {settings.embedding_dim}, got {result['dimension']}")
            
            if result["num_entities"] > 0:
                print(f"   ✅ Collection HAS DATA")
                
                # Get sample records with all fields
                try:
                    coll = Collection(collection_name)
                    coll.load()
                    
                    # Determine which fields to retrieve (only request fields that exist)
                    if collection_name == settings.milvus_collection:
                        output_fields = [
                            "id", "clause_id", "contract_id", "clause_type",
                            "text", "rdf_uri", "graph_uri"
                        ]
                    else:
                        # v2 and Docling both have summary, key_points, structured_summary
                        output_fields = [
                            "id", "clause_id", "contract_id", "clause_type",
                            "text", "summary", "key_points", "structured_summary",
                            "rdf_uri", "graph_uri"
                        ]
                    
                    samples = coll.query(
                        expr="",
                        limit=min(3, result["num_entities"]),  # Get up to 3 samples
                        output_fields=output_fields
                    )
                    
                    if samples:
                        print(f"\n   📝 Sample Records ({len(samples)} of {result['num_entities']}):")
                        for i, record in enumerate(samples, 1):
                            print(f"\n      ┌─ Sample {i} ─" + "─" * 60)
                            for field in output_fields:
                                value = record.get(field, "N/A")
                                
                                # Format value for display
                                if field == "text":
                                    # Truncate long text
                                    text_str = str(value) if value != "N/A" else "N/A"
                                    if len(text_str) > 150:
                                        text_str = text_str[:147] + "..."
                                    print(f"      │ {field:20}: {text_str}")
                                elif field in ["summary", "key_points", "structured_summary"]:
                                    # Handle JSON strings or text
                                    if value and value != "N/A":
                                        try:
                                            import json
                                            # Try to parse as JSON
                                            parsed = json.loads(str(value))
                                            if isinstance(parsed, list):
                                                # Key points as list
                                                if len(parsed) > 3:
                                                    points_str = ", ".join(str(p) for p in parsed[:3]) + f" ... ({len(parsed)} total)"
                                                else:
                                                    points_str = ", ".join(str(p) for p in parsed)
                                                print(f"      │ {field:20}: {points_str}")
                                            elif isinstance(parsed, dict):
                                                # Structured summary as dict
                                                keys = list(parsed.keys())[:3]
                                                summary_str = ", ".join(f"{k}: {parsed[k]}" for k in keys)
                                                if len(parsed) > 3:
                                                    summary_str += f" ... ({len(parsed)} fields)"
                                                print(f"      │ {field:20}: {summary_str}")
                                            else:
                                                # Plain string
                                                val_str = str(value)
                                                if len(val_str) > 100:
                                                    val_str = val_str[:97] + "..."
                                                print(f"      │ {field:20}: {val_str}")
                                        except (json.JSONDecodeError, TypeError):
                                            # Not JSON, treat as plain string
                                            val_str = str(value)
                                            if len(val_str) > 100:
                                                val_str = val_str[:97] + "..."
                                            print(f"      │ {field:20}: {val_str}")
                                    else:
                                        print(f"      │ {field:20}: N/A")
                                elif field in ["rdf_uri", "graph_uri"]:
                                    # Truncate long URIs
                                    uri_str = str(value) if value != "N/A" else "N/A"
                                    if len(uri_str) > 80:
                                        uri_str = uri_str[:77] + "..."
                                    print(f"      │ {field:20}: {uri_str}")
                                else:
                                    # Regular fields
                                    print(f"      │ {field:20}: {value}")
                            print(f"      └" + "─" * 70)
                except Exception as e:
                    print(f"   ⚠️  Could not retrieve samples: {e}")
                    import traceback
                    print(f"      Error: {traceback.format_exc()}")
            else:
                print(f"   ⚠️  Collection is EMPTY (no data)")
    
    # Summary
    print(f"\n{'=' * 70}")
    print("📊 SUMMARY")
    print(f"{'=' * 70}")
    
    for result in results:
        status = "✅" if result["exists"] and result["num_entities"] > 0 and result["dimension"] == settings.embedding_dim else "⚠️"
        print(f"{status} {result['name']}: {result['num_entities']:,} entities, dim={result['dimension']}")
    
    # Find the collection with data and correct dimension
    valid_collections = [
        r for r in results 
        if r["exists"] and r["num_entities"] > 0 and r["dimension"] == settings.embedding_dim
    ]
    
    if valid_collections:
        print(f"\n✅ Found {len(valid_collections)} collection(s) with data and dimension {settings.embedding_dim}:")
        for r in valid_collections:
            print(f"   • {r['name']}: {r['num_entities']:,} entities")
    else:
        print(f"\n⚠️  No collections found with data and dimension {settings.embedding_dim}")
        print(f"   → Run the ingestion pipeline to populate the collection")
    
    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
