#!/usr/bin/env python3
"""
Setup Fuseki Dataset

Creates the contracts dataset in Apache Jena Fuseki with TDB2 backend.
This script should be run once when setting up the system.

Usage:
    uv run python setup_fuseki.py
    uv run python setup_fuseki.py --dataset my_dataset
    uv run python setup_fuseki.py --check  # Just check if exists
"""

import argparse
import sys
from pathlib import Path

import httpx

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

# Configuration
FUSEKI_URL = "http://localhost:3030"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin123"


def check_fuseki_running() -> bool:
    """Check if Fuseki server is running."""
    try:
        response = httpx.get(f"{FUSEKI_URL}/$/ping", timeout=5.0)
        return response.status_code == 200
    except httpx.ConnectError:
        return False


def list_datasets() -> list[str]:
    """List existing datasets."""
    try:
        response = httpx.get(
            f"{FUSEKI_URL}/$/datasets",
            auth=(ADMIN_USER, ADMIN_PASSWORD),
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            return [ds["ds.name"].lstrip("/") for ds in data.get("datasets", [])]
        return []
    except Exception:
        return []


def dataset_exists(name: str) -> bool:
    """Check if a dataset exists."""
    return name in list_datasets()


def create_dataset(name: str, db_type: str = "tdb2") -> bool:
    """
    Create a new dataset in Fuseki.
    
    Args:
        name: Dataset name
        db_type: Database type (tdb2, tdb, mem)
        
    Returns:
        True if created successfully
    """
    if dataset_exists(name):
        print(f"⚠️  Dataset '{name}' already exists")
        return True
    
    print(f"📦 Creating dataset '{name}' with {db_type} backend...")
    
    response = httpx.post(
        f"{FUSEKI_URL}/$/datasets",
        auth=(ADMIN_USER, ADMIN_PASSWORD),
        data={"dbName": name, "dbType": db_type},
        timeout=30.0,
    )
    
    if response.status_code in (200, 201):
        print(f"✅ Dataset '{name}' created successfully")
        return True
    else:
        print(f"❌ Failed to create dataset: {response.status_code}")
        print(f"   Response: {response.text}")
        return False


def delete_dataset(name: str) -> bool:
    """Delete a dataset (use with caution!)."""
    if not dataset_exists(name):
        print(f"⚠️  Dataset '{name}' does not exist")
        return True
    
    print(f"🗑️  Deleting dataset '{name}'...")
    
    response = httpx.delete(
        f"{FUSEKI_URL}/$/datasets/{name}",
        auth=(ADMIN_USER, ADMIN_PASSWORD),
        timeout=30.0,
    )
    
    if response.status_code in (200, 204):
        print(f"✅ Dataset '{name}' deleted")
        return True
    else:
        print(f"❌ Failed to delete dataset: {response.status_code}")
        return False


def get_dataset_stats(name: str) -> dict:
    """Get statistics for a dataset."""
    response = httpx.get(
        f"{FUSEKI_URL}/$/datasets/{name}",
        auth=(ADMIN_USER, ADMIN_PASSWORD),
        timeout=10.0,
    )
    
    if response.status_code == 200:
        return response.json()
    return {}


def main():
    parser = argparse.ArgumentParser(description="Setup Fuseki dataset")
    parser.add_argument(
        "--dataset", "-d",
        default="contracts",
        help="Dataset name (default: contracts)",
    )
    parser.add_argument(
        "--db-type",
        default="tdb2",
        choices=["tdb2", "tdb", "mem"],
        help="Database type (default: tdb2)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check if dataset exists",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all datasets",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the dataset (use with caution!)",
    )
    
    args = parser.parse_args()
    
    # Check Fuseki is running
    print("🔍 Checking Fuseki server...")
    if not check_fuseki_running():
        print("❌ Fuseki server is not running!")
        print("   Start it with: cd docker && docker-compose up -d fuseki")
        sys.exit(1)
    print("✅ Fuseki server is running")
    
    # List datasets
    if args.list:
        datasets = list_datasets()
        print(f"\n📋 Datasets ({len(datasets)}):")
        for ds in datasets:
            print(f"   - {ds}")
        return
    
    # Check only
    if args.check:
        exists = dataset_exists(args.dataset)
        print(f"Dataset '{args.dataset}': {'✅ exists' if exists else '❌ does not exist'}")
        sys.exit(0 if exists else 1)
    
    # Delete dataset
    if args.delete:
        confirm = input(f"⚠️  Are you sure you want to delete '{args.dataset}'? (yes/no): ")
        if confirm.lower() == "yes":
            success = delete_dataset(args.dataset)
            sys.exit(0 if success else 1)
        else:
            print("Cancelled")
            return
    
    # Create dataset
    success = create_dataset(args.dataset, args.db_type)
    
    if success:
        stats = get_dataset_stats(args.dataset)
        print(f"\n📊 Dataset Info:")
        print(f"   Name: {args.dataset}")
        print(f"   URL: {FUSEKI_URL}/{args.dataset}")
        print(f"   Query: {FUSEKI_URL}/{args.dataset}/query")
        print(f"   Update: {FUSEKI_URL}/{args.dataset}/update")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
