#!/usr/bin/env python3
"""
Migrate Milvus collection to new schema with RDF linking fields.

This script:
1. Backs up existing data
2. Drops the old collection
3. Creates new collection with updated schema
4. Optionally restores data (with default values for new fields)

Usage:
    uv run python scripts/migrate_milvus_schema.py [--restore]
"""

import argparse
import sys
from pathlib import Path

# Add agents to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from pymilvus import connections, Collection, utility
from config import get_settings
from vector_store import MilvusVectorStore
import structlog

logger = structlog.get_logger()


def backup_collection(collection_name: str) -> list[dict]:
    """Backup existing collection data."""
    if not utility.has_collection(collection_name):
        logger.info("No existing collection to backup", collection=collection_name)
        return []
    
    collection = Collection(collection_name)
    collection.load()
    
    # Query all data
    results = collection.query(
        expr="id != ''",
        output_fields=["id", "clause_id", "contract_id", "clause_type", "text", "embedding"],
    )
    
    logger.info("Backed up collection data", collection=collection_name, count=len(results))
    return results


def drop_collection(collection_name: str) -> None:
    """Drop existing collection."""
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)
        logger.info("Dropped old collection", collection=collection_name)
    else:
        logger.info("No collection to drop", collection=collection_name)


def restore_data(vector_store: MilvusVectorStore, backup_data: list[dict]) -> None:
    """Restore data to new collection with default values for new fields."""
    if not backup_data:
        logger.info("No data to restore")
        return
    
    logger.info("Restoring data to new collection", count=len(backup_data))
    
    # Prepare data with new fields
    ids = []
    clause_ids = []
    contract_ids = []
    clause_types = []
    texts = []
    rdf_uris = []
    graph_uris = []
    embeddings = []
    
    for item in backup_data:
        ids.append(item["id"])
        clause_ids.append(item["clause_id"])
        contract_ids.append(item["contract_id"])
        clause_types.append(item["clause_type"])
        texts.append(item["text"])
        # Default values for new fields
        rdf_uris.append(f"http://example.org/clause/{item['clause_id']}")
        graph_uris.append(f"http://example.org/contract/{item['contract_id']}")
        embeddings.append(item["embedding"])
    
    # Insert in batches
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        batch_end = min(i + batch_size, len(ids))
        
        data = [
            ids[i:batch_end],
            clause_ids[i:batch_end],
            contract_ids[i:batch_end],
            clause_types[i:batch_end],
            texts[i:batch_end],
            rdf_uris[i:batch_end],
            graph_uris[i:batch_end],
            embeddings[i:batch_end],
        ]
        
        vector_store.collection.insert(data)
        logger.info("Inserted batch", start=i, end=batch_end)
    
    vector_store.collection.flush()
    logger.info("Data restoration complete", total=len(ids))


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(description="Migrate Milvus collection schema")
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore backed up data after migration",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="Only backup data without dropping collection",
    )
    args = parser.parse_args()
    
    settings = get_settings()
    collection_name = settings.milvus_collection
    
    print(f"\n{'='*70}")
    print(f"  Milvus Schema Migration")
    print(f"{'='*70}\n")
    print(f"Collection: {collection_name}")
    print(f"Host: {settings.milvus_host}:{settings.milvus_port}")
    print(f"Restore data: {args.restore}")
    print(f"Backup only: {args.backup_only}\n")
    
    # Connect to Milvus
    connections.connect(
        alias="default",
        host=settings.milvus_host,
        port=settings.milvus_port,
    )
    logger.info("Connected to Milvus")
    
    # Step 1: Backup existing data
    print("Step 1: Backing up existing data...")
    backup_data = backup_collection(collection_name)
    print(f"✓ Backed up {len(backup_data)} records\n")
    
    if args.backup_only:
        print("Backup complete. Exiting without dropping collection.")
        return
    
    # Step 2: Drop old collection
    print("Step 2: Dropping old collection...")
    drop_collection(collection_name)
    print("✓ Old collection dropped\n")
    
    # Step 3: Create new collection with updated schema
    print("Step 3: Creating new collection with updated schema...")
    vector_store = MilvusVectorStore(settings)
    print("✓ New collection created with 8 fields:\n")
    print("  - id (primary key)")
    print("  - clause_id")
    print("  - contract_id")
    print("  - clause_type")
    print("  - text")
    print("  - rdf_uri (NEW)")
    print("  - graph_uri (NEW)")
    print("  - embedding\n")
    
    # Step 4: Restore data if requested
    if args.restore and backup_data:
        print("Step 4: Restoring data...")
        restore_data(vector_store, backup_data)
        print(f"✓ Restored {len(backup_data)} records\n")
    elif args.restore:
        print("Step 4: No data to restore\n")
    else:
        print("Step 4: Skipping data restoration (use --restore flag to restore)\n")
    
    print(f"{'='*70}")
    print("  Migration Complete!")
    print(f"{'='*70}\n")
    
    if not args.restore and backup_data:
        print("⚠️  Note: Data was backed up but not restored.")
        print("   Run with --restore flag to restore the data.\n")


if __name__ == "__main__":
    main()


